"""Part 4: WebRTC signalling bodies and the data-channel / WebSocket message protocol (tagged unions on `type`)."""

from __future__ import annotations

from typing import Literal

import msgspec

from claimvoice.schemas.base import Lang, Model
from claimvoice.schemas.calls import CallMode, Flag, HandoffInfo, Slot, StageInfo, Turn

# ------------------------------------------------------------------ HTTP signalling


class SdpOffer(Model):
    sdp: str
    type: Literal["offer"]
    pc_id: str | None = None  # present on renegotiation
    restart_pc: bool = False


class SdpAnswer(Model):
    sdp: str
    type: Literal["answer"]
    pc_id: str


class IceCandidate(Model):
    candidate: str
    sdp_mid: str | None = None
    sdp_m_line_index: int | None = None


class IcePatch(Model):
    pc_id: str
    candidates: list[IceCandidate]


# ------------------------------------------------------------------ data channel messages (JSON text frames)
# The browser additionally sends the raw text "ping-<ms>" about once a second once the channel is open (Pipecat
# keep-alive); a gap over 3 s marks the caller as disconnected.


class Msg(msgspec.Struct, rename="camel", kw_only=True, tag_field="type"):
    pass


# client -> server


class ClientHello(Msg, tag="client.hello"):
    mode: CallMode
    language: Lang | Literal["auto"]
    recognition: Literal["on_device", "cloud", "none"]  # what the browser's speech recognition offers
    voices: list[str] = []  # speechSynthesis voice names available for en-CA/fr-CA


class CallerText(Msg, tag="caller.text"):
    text: str
    final: bool  # only final text drives the dialogue; interim text feeds the live caption
    language: Lang
    confidence: float | None = None
    started_at_ms: int | None = None
    ended_at_ms: int | None = None  # end of speech, for turn timing


class CallerBargeIn(Msg, tag="caller.barge_in"):
    at_ms: int


class LineSpoken(Msg, tag="line.spoken"):
    """Browser speech synthesis progress for a line turn (browser_speech mode)."""

    turn_id: str
    event: Literal["start", "end", "cancelled"]
    at_ms: int


class CallerHangup(Msg, tag="caller.hangup"):
    pass


ClientMessage = ClientHello | CallerText | CallerBargeIn | LineSpoken | CallerHangup

# server -> client


class CallReady(Msg, tag="call.ready"):
    call_id: str
    mode: CallMode
    language: Lang
    stage: StageInfo


class LineSay(Msg, tag="line.say"):
    """A line turn. In browser_speech mode the browser speaks it; in voice mode audio arrives on the track and this
    is the caption."""

    turn_id: str
    text: str
    language: Lang
    voice_lang: str  # BCP-47 for speechSynthesis: "en-CA" | "fr-CA"
    interruptible: bool = True
    expects_answer: bool = True


class LineStop(Msg, tag="line.stop"):
    turn_id: str
    reason: Literal["barge_in", "takeover", "hangup"]


class TranscriptTurn(Msg, tag="transcript.turn"):
    turn: Turn


class TranscriptPartial(Msg, tag="transcript.partial"):
    speaker: Literal["caller"]
    text: str


class ClaimFileSlot(Msg, tag="claim_file.slot"):
    slot: Slot
    progress: float


class CallStage(Msg, tag="call.stage"):
    stage: StageInfo


class CallFlagMsg(Msg, tag="call.flag"):
    flag: Flag


class CallNotice(Msg, tag="call.notice"):
    kind: Literal[
        "recording_on",
        "recording_off",
        "recording_paused",
        "recording_resumed",
        "card_number_removed",
        "photo_link_sent",
        "waiting_for_person",
        "person_joined",
        "back_with_line",
        "language_switched",
        "connection_weak",
    ]
    text: str  # caption shown to the caller, in the call's language


class CallHandoff(Msg, tag="call.handoff"):
    handoff: HandoffInfo


class CallEnded(Msg, tag="call.ended"):
    reason: str
    claim_number: str | None
    summary: str | None
    next_steps: list[str]


class TurnMetrics(Msg, tag="turn.metrics"):
    """Timing for the eval harness and the latency report; the web app never renders it."""

    turn_id: str
    stt_ms: float
    understand_ms: float
    tools_ms: float
    plan_ms: float
    first_audio_ms: float
    total_ms: float


ServerMessage = (
    CallReady
    | LineSay
    | LineStop
    | TranscriptTurn
    | TranscriptPartial
    | ClaimFileSlot
    | CallStage
    | CallFlagMsg
    | CallNotice
    | CallHandoff
    | CallEnded
    | TurnMetrics
)

client_decoder = msgspec.json.Decoder(ClientMessage)
server_decoder = msgspec.json.Decoder(ServerMessage)
