"""The mid-call tools the dialogue engine may call, each with its budget, timeout and fallback (docs/ARCHITECTURE.md):

| Tool | Budget | On timeout or error |
|---|---:|---|
| policy lookup | 300 ms | "One moment" and ask again; twice -> hand-off (`tool_failed`) |
| identity check | 200 ms | treated as "not confirmed yet"; ask again |
| coverage check | 300 ms | "Your adjuster will go through your coverage with you." |
| photo-link text | 600 ms | "Your adjuster will send the link instead." |
| weather lookup | 400 ms | no surge match, no weather sign |

Every call returns the value (or the fallback) plus a `ToolCallRecord` for `CallSink.tool_called`.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from claimvoice import clock
from claimvoice.contracts import CoverageSummary, PolicyDirectory, PolicyMatch, ToolCallRecord
from claimvoice.tools.base import BUDGETS_MS, ToolTiming, run_tool
from claimvoice.tools.sms import SmsReceipt, SmsSender, get_sms_sender, mask_phone
from claimvoice.tools.weather import BundledWeather, WeatherAlert, WeatherFeed

TOOL_LABELS: dict[str, dict[str, str]] = {
    "policy_lookup": {"ok": "Policy found", "miss": "Policy not found", "fail": "Policy lookup didn't answer"},
    "identity_check": {
        "ok": "Identity checked",
        "miss": "Identity detail didn't match",
        "fail": "Identity check didn't answer",
    },
    "coverage_check": {
        "ok": "Coverage looked up",
        "miss": "Coverage looked up",
        "fail": "Coverage check didn't answer",
    },
    "photo_link_sms": {"ok": "Photo link texted", "miss": "Photo link not sent", "fail": "Text message didn't send"},
    "weather_lookup": {
        "ok": "Weather event matched",
        "miss": "No weather event on record",
        "fail": "Weather lookup didn't answer",
    },
}


def _record(t: ToolTiming, at_ms: int, *, found: bool) -> ToolCallRecord:
    labels = TOOL_LABELS.get(t.tool, {"ok": t.tool, "miss": t.tool, "fail": t.tool})
    summary = labels["ok" if t.ok and found else ("miss" if t.ok else "fail")]
    return ToolCallRecord(t.tool, t.ok, round(t.elapsed_ms, 2), t.budget_ms, t.timed_out, at_ms, summary)


@dataclass
class Toolbox:
    policies: PolicyDirectory
    org_id: str
    sms: SmsSender = field(default_factory=get_sms_sender)
    weather: WeatherFeed | None = None
    web_origin: str = "http://localhost:3040"
    budgets: dict[str, int] = field(default_factory=lambda: dict(BUDGETS_MS))

    def __post_init__(self) -> None:
        if self.weather is None:
            self.weather = BundledWeather(clock.today())

    async def find_policy(
        self, *, at_ms: int, policy_number: str | None = None, phone: str | None = None
    ) -> tuple[PolicyMatch | None, ToolCallRecord]:
        value, t = await run_tool(
            "policy_lookup",
            lambda: self.policies.find_policy(self.org_id, policy_number=policy_number, phone=phone),
            fallback=None,
            budget_ms=self.budgets["policy_lookup"],
        )
        return value, _record(t, at_ms, found=value is not None)

    async def verify(
        self, policy_id: str, *, at_ms: int, date_of_birth: date | None = None, postal_code: str | None = None
    ) -> tuple[bool | None, ToolCallRecord]:
        value, t = await run_tool(
            "identity_check",
            lambda: self.policies.verify_identity(
                self.org_id, policy_id, date_of_birth=date_of_birth, postal_code=postal_code
            ),
            fallback=None,
            budget_ms=self.budgets["identity_check"],
        )
        return value, _record(t, at_ms, found=bool(value))

    async def coverage(
        self, policy_id: str, loss_type: str, loss_date: date, *, at_ms: int
    ) -> tuple[CoverageSummary | None, ToolCallRecord]:
        value, t = await run_tool(
            "coverage_check",
            lambda: self.policies.coverage(self.org_id, policy_id, loss_type, loss_date),
            fallback=None,
            budget_ms=self.budgets["coverage_check"],
        )
        return value, _record(t, at_ms, found=value is not None)

    async def send_photo_link(
        self, to: str, *, at_ms: int, call_id: str, language: str, org_name: str
    ) -> tuple[tuple[SmsReceipt, str] | None, ToolCallRecord]:
        token = secrets.token_urlsafe(24)
        url = f"{self.web_origin.rstrip('/')}/p/{token}"
        body = (
            f"{org_name} : téléversez les photos de vos dommages ici : {url} (lien valide 72 heures)"
            if language == "fr"
            else f"{org_name}: upload photos of the damage here: {url} (link works for 72 hours)"
        )

        async def send() -> tuple[SmsReceipt, str]:
            receipt = await self.sms.send(to, body, org_id=self.org_id, call_id=call_id)
            return receipt, token

        value, t = await run_tool("photo_link_sms", send, fallback=None, budget_ms=self.budgets["photo_link_sms"])
        return value, _record(t, at_ms, found=value is not None)

    async def weather_events(
        self, region: str, at: datetime, *, at_ms: int, kinds: Sequence[str] = ()
    ) -> tuple[list[WeatherAlert], ToolCallRecord]:
        feed = self.weather
        assert feed is not None

        async def look() -> list[WeatherAlert]:
            alerts = await feed.alerts(region, at)
            if not alerts:  # a loss reported the morning after still matches the overnight event
                from datetime import timedelta

                alerts = await feed.alerts(region, at - timedelta(hours=10))
            return [a for a in alerts if not kinds or a.kind in kinds]

        empty: list[WeatherAlert] = []
        value, t = await run_tool("weather_lookup", look, fallback=empty, budget_ms=self.budgets["weather_lookup"])
        return value, _record(t, at_ms, found=bool(value))


__all__ = ["TOOL_LABELS", "Toolbox", "mask_phone"]
