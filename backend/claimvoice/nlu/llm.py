"""Cloud language understanding through LiteLLM (optional: `make setup-ai`, `LLM_FAKE=false` and a free-tier key).

The model only reads: it returns an intent, values for the fields the stage expects (each with the exact words it
heard them in), and safety/distress signals, as JSON matching a schema. It never chooses what happens next. Every
answer is checked before use: values for fields that weren't asked for are dropped, a span must point at the words it
quotes, and safety words found by the rules are never overruled. On a timeout (600 ms), an error or an invalid answer
the rule-based reader answers instead, so a slow service never stalls the call.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from claimvoice.dialogue.slots import display
from claimvoice.nlu.base import Intent, LanguageUnderstanding, LlmClient, NluRequest, NluResult, SlotValue
from claimvoice.nlu.fake import FakeLlm, FakeUnderstanding

SYSTEM = (
    "You read one turn of an insurance claim phone call (English or Canadian French) and return JSON only. "
    "Report what the caller said; never decide what to do next and never add facts. For each expected field you "
    "find, copy the exact words from the utterance into `quote`. Dates are ISO (YYYY-MM-DD) relative to `today`, "
    "times are HH:MM 24-hour, yes/no fields are true/false. Use null when unsure."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"enum": [i.value for i in Intent]},
        "values": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {},
                    "quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["key", "value", "quote"],
            },
        },
        "urgentSafety": {"type": "boolean"},
        "safetyReason": {"type": ["string", "null"]},
        "distress": {"type": "number"},
        "language": {"enum": ["en", "fr", None]},
    },
    "required": ["intent", "values"],
}


@dataclass
class LiteLlmClient:
    """`LlmClient` over LiteLLM's async completion (any free-tier provider LiteLLM supports)."""

    model: str
    name: str = "litellm"

    async def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        timeout_ms: int = 600,
        temperature: float = 0.0,
    ) -> str:
        import litellm  # optional dependency (pip install ".[ai]")

        kwargs: dict[str, Any] = {}
        if json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await litellm.acompletion(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            timeout=timeout_ms / 1000,
            **kwargs,
        )
        return str(resp.choices[0].message.content or "")


@dataclass
class LlmUnderstanding:
    """Language understanding backed by an `LlmClient`, checked against the rules and falling back to them."""

    client: LlmClient
    timeout_ms: int = 600
    rules: FakeUnderstanding = field(default_factory=FakeUnderstanding)

    async def understand(self, request: NluRequest) -> NluResult:
        base = self.rules.understand_sync(request)
        payload = {
            "today": (request.now.date().isoformat() if request.now else None),
            "language": request.language,
            "stage": request.stage,
            "asked": request.asked,
            "expected": [{"key": s.key, "kind": s.kind, "choices": list(s.choices)} for s in request.expecting],
            "alreadyKnown": {k: v for k, v in request.filled.items() if isinstance(v, str | int | float | bool)},
            "utterance": request.utterance,
        }
        try:
            raw = await asyncio.wait_for(
                self.client.complete(
                    SYSTEM, json.dumps(payload, ensure_ascii=False), json_schema=SCHEMA, timeout_ms=self.timeout_ms
                ),
                timeout=self.timeout_ms / 1000,
            )
            doc = json.loads(raw)
        except Exception:
            return base
        return self.merge(request, base, doc)

    @staticmethod
    def merge(request: NluRequest, base: NluResult, doc: Mapping[str, Any]) -> NluResult:
        expected = {s.key for s in request.expecting}
        text = request.utterance
        values: dict[str, SlotValue] = {v.key: v for v in base.slots}
        for item in doc.get("values") or []:
            key, quote = item.get("key"), str(item.get("quote") or "")
            if key not in expected or key in values or not quote:
                continue
            start = text.find(quote)
            if start < 0:
                continue  # the quote must be words the caller actually said
            value = item.get("value")
            if value is None:
                continue
            old = request.filled.get(key)
            values[key] = SlotValue(
                key,
                value,
                display(key, value, request.language),
                float(item.get("confidence") or 0.75),
                (start, start + len(quote)),
                corrects=old is not None and old != value,
            )
        try:
            intent = Intent(doc.get("intent", base.intent.value))
        except ValueError:
            intent = base.intent
        if base.intent in (Intent.HANDOFF_REQUEST, Intent.CORRECTION):
            intent = base.intent  # rules win on the two intents with consequences
        urgent = base.urgent_safety or bool(doc.get("urgentSafety"))
        return NluResult(
            intent=intent,
            slots=tuple(values.values()),
            language=base.language or (doc.get("language") if doc.get("language") != request.language else None),
            distress=max(base.distress, min(1.0, float(doc.get("distress") or 0.0))),
            urgent_safety=urgent,
            safety_reason=base.safety_reason or (doc.get("safetyReason") if urgent else None),
            confidence=max(base.confidence, 0.8),
            source="llm",
            topic=base.topic,
        )


def get_understanding() -> LanguageUnderstanding:
    """The configured reader: the rules (default, offline) or the cloud model checked against them."""
    from claimvoice.config import get_settings

    s = get_settings()
    if s.llm_fake or not any((s.groq_api_key, s.gemini_api_key, s.openrouter_api_key)):
        return FakeUnderstanding()
    return LlmUnderstanding(LiteLlmClient(s.llm_model))


def get_llm() -> LlmClient:
    from claimvoice.config import get_settings

    s = get_settings()
    if s.llm_fake or not any((s.groq_api_key, s.gemini_api_key, s.openrouter_api_key)):
        return FakeLlm()
    return LiteLlmClient(s.llm_model)
