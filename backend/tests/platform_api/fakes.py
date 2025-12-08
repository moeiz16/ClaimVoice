"""A recording stand-in for the voice runtime (`LineRuntime`), so line controls can be tested without Pipecat."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeRuntime:
    live: set[str] = field(default_factory=set)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def is_live(self, call_id: str) -> bool:
        return call_id in self.live

    def _log(self, action: str, call_id: str, **kw: Any) -> None:
        self.calls.append((action, call_id, kw))

    def of(self, name: str) -> list[tuple[str, dict[str, Any]]]:
        return [(c, kw) for n, c, kw in self.calls if n == name]

    async def whisper(self, call_id: str, text: str, *, from_name: str) -> None:
        self._log("whisper", call_id, text=text, from_name=from_name)

    async def take_over(self, call_id: str, *, user_id: str, name: str) -> None:
        self._log("take_over", call_id, user_id=user_id, name=name)

    async def say_as_person(self, call_id: str, text: str, *, user_id: str, name: str) -> str:
        self._log("say", call_id, text=text)
        return "turn-from-runtime"

    async def hand_back(self, call_id: str, *, user_id: str) -> None:
        self._log("hand_back", call_id)

    async def hang_up(self, call_id: str, *, reason: str, by_user_id: str | None) -> None:
        self._log("hang_up", call_id, reason=reason)
        self.live.discard(call_id)
        from claimvoice.calls.closing import close_call
        from claimvoice.platform import db

        async with db.sessionmaker()() as s:
            from claimvoice.calls.models import Call

            org_id = (await s.get(Call, call_id)).org_id  # type: ignore[union-attr]
        await close_call(org_id, call_id, None, reason="ended_by_person")

    async def prepare(self, call_id: str, **kw: Any) -> None:
        self._log(
            "prepare", call_id, **{k: v for k, v in kw.items() if k in ("mode", "language", "region", "scenario")}
        )
        self.live.add(call_id)

    async def answer_offer(
        self, call_id: str, sdp: str, type: str, pc_id: str | None, restart_pc: bool
    ) -> Mapping[str, Any]:
        self._log("offer", call_id, sdp=sdp)
        return {"sdp": "v=0 answer", "type": "answer", "pcId": pc_id or "pc-1"}

    async def add_ice(self, call_id: str, pc_id: str, candidates: Sequence[Mapping[str, Any]]) -> None:
        self._log("ice", call_id, count=len(candidates))

    async def run_websocket(self, call_id: str, socket: Any) -> None:
        self._log("ws", call_id)
        await socket.close(code=1000)

    async def adopt_sample_line(self, call_id: str, **kw: Any) -> None:
        self._log("adopt", call_id, resume=kw.get("resume_after_turn"))
        self.live.add(call_id)

    async def nudge(self, call_id: str) -> None:
        self._log("nudge", call_id)
