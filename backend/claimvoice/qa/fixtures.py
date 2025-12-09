"""Reviewed calls (`qa/data/reviewed_calls.yml`) as the turns, events and claim-file values the scorer reads.

Calls handled by people, or by an older script, with known problems and the quality lead's verdict on each rubric
item. The eval measures the scorer's agreement with those verdicts; the seed uses them for the review queue."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from claimvoice.contracts import SlotRecord, Speaker, TurnRecord
from claimvoice.dialogue.slots import display
from claimvoice.nlu.fake import detect_language

DATA = Path(__file__).parent / "data" / "reviewed_calls.yml"
_NS = uuid.UUID("6f1d3a52-41c8-4b55-9d3c-7a2f0c5e9b10")


@dataclass(frozen=True)
class ReviewedCall:
    key: str
    title: str
    region: str
    language: str
    person: str | None
    turns: tuple[TurnRecord, ...]
    events: tuple[dict[str, Any], ...]
    slots: dict[str, SlotRecord]
    labels: dict[str, str]  # rubric key -> "pass" | "fail" | "na"


def _build(raw: dict[str, Any]) -> ReviewedCall:
    key = raw["key"]
    lang = raw.get("language", "en")
    rows = raw["turns"]
    redacted = set(raw.get("redacted_turns", []))
    turns: list[TurnRecord] = []
    for i, (speaker, sec, text, stage) in enumerate(rows):
        nxt = rows[i + 1][1] if i + 1 < len(rows) else sec + 3
        sp = Speaker(speaker)
        language = (detect_language(text) or lang) if sp is Speaker.CALLER else lang
        turns.append(
            TurnRecord(
                turn_id=str(uuid.uuid5(_NS, f"{key}-{i}")),
                seq=i + 1,
                speaker=sp,
                text=text,
                language=language,
                at_ms=int(sec * 1000),
                end_ms=int(max(nxt - 0.3, sec + 0.5) * 1000),
                stage=stage,
                redactions=1 if i in redacted else 0,
                speaker_name=raw.get("person") if sp is Speaker.PERSON else None,
            )
        )
    events = [{"kind": "answered", "atMs": 0, "data": {"region": raw["region"], "language": lang}}]
    events += [dict(e) for e in raw.get("events", [])]
    events.append({"kind": "ended", "atMs": turns[-1].end_ms, "data": {"reason": "completed"}})
    slots = {
        k: SlotRecord(k, v, display(k, v, lang), 0.9, "heard" if k != "identity_check" else "tool", None, None)
        for k, v in (raw.get("slots") or {}).items()
    }
    return ReviewedCall(
        key,
        raw.get("title", key),
        raw["region"],
        lang,
        raw.get("person"),
        tuple(turns),
        tuple(events),
        slots,
        dict(raw.get("labels", {})),
    )


@cache
def reviewed_calls() -> dict[str, ReviewedCall]:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    return {c["key"]: _build(c) for c in doc["calls"]}
