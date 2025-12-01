"""Text messages (the photo link). Fake by default: messages go to an in-memory outbox the demo can show."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from claimvoice import clock


def mask_phone(e164: str) -> str:
    digits = [c for c in e164 if c.isdigit()]
    return "•••-•••-" + "".join(digits[-4:]) if len(digits) >= 4 else "•••"


@dataclass(frozen=True, slots=True)
class SmsReceipt:
    message_id: str
    to_masked: str
    status: str  # "queued" | "sent" | "failed"
    sent_at: datetime


@runtime_checkable
class SmsSender(Protocol):
    name: str

    async def send(self, to: str, body: str, *, org_id: str, call_id: str | None = None) -> SmsReceipt: ...


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    org_id: str
    call_id: str | None
    to: str
    body: str
    receipt: SmsReceipt


@dataclass
class FakeSms:
    """Never sends anything. Keeps the last 200 messages so the demo can open the photo link it 'texted'."""

    name: str = "fake-sms"
    outbox: list[OutboxMessage] = field(default_factory=list)

    async def send(self, to: str, body: str, *, org_id: str, call_id: str | None = None) -> SmsReceipt:
        message_id = (
            "sms_" + hashlib.sha256(f"{org_id}|{call_id}|{to}|{body}|{len(self.outbox)}".encode()).hexdigest()[:16]
        )
        receipt = SmsReceipt(message_id, mask_phone(to), "sent", clock.now())
        self.outbox.append(OutboxMessage(org_id, call_id, to, body, receipt))
        del self.outbox[:-200]
        return receipt

    def for_call(self, call_id: str) -> list[OutboxMessage]:
        return [m for m in self.outbox if m.call_id == call_id]
