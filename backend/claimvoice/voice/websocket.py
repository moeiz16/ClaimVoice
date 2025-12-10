"""The WebSocket fallback transport (docs/API_CONTRACT.md §4.4).

Used when WebRTC can't connect within 8 s or the browser has no `RTCPeerConnection`. Text frames carry the same JSON
messages as the data channel (no `ping-` keep-alive: the WebSocket's own ping applies). Binary frames from the
caller are 16-bit little-endian PCM, 16 kHz mono, 20 ms; in `voice` mode Silero VAD cuts them into segments for
speech-to-text, and the line's audio goes back as 24 kHz PCM16 binary frames."""

from __future__ import annotations

import json
from typing import Any

import structlog

from claimvoice.contracts import CallMode
from claimvoice.voice.session import CallSession

log = structlog.get_logger("claimvoice.voice")
IN_RATE = 16000


class Segmenter:
    """Silero VAD over raw PCM: reports speech start and returns the finished segment at speech end."""

    def __init__(self) -> None:
        from pipecat.audio.vad.vad_analyzer import VADState

        from claimvoice.voice.pipeline import vad_analyzer

        self.vad = vad_analyzer()
        self.vad.set_sample_rate(IN_RATE)
        self.VADState = VADState
        self.state = VADState.QUIET
        self.buffer = bytearray()

    async def feed(self, pcm: bytes) -> tuple[bool, bytes | None]:
        """(speech started, finished segment or None)."""
        new = await self.vad.analyze_audio(pcm)
        started = new == self.VADState.SPEAKING and self.state != self.VADState.SPEAKING
        if new in (self.VADState.STARTING, self.VADState.SPEAKING, self.VADState.STOPPING):
            self.buffer.extend(pcm)
        done: bytes | None = None
        if new == self.VADState.QUIET and self.state in (self.VADState.SPEAKING, self.VADState.STOPPING):
            done, self.buffer = bytes(self.buffer), bytearray()
        self.state = new
        return started, done


async def run_websocket(session: CallSession, socket: Any) -> None:
    """Serve one caller over an accepted Litestar WebSocket until it closes or the call ends."""

    async def send_json(msg: dict[str, Any]) -> None:
        await socket.send_text(json.dumps(msg, ensure_ascii=False))

    async def send_audio(pcm: bytes) -> None:
        await socket.send_bytes(pcm)

    session.send_json = send_json
    session.send_audio = send_audio
    segmenter: Segmenter | None = None
    try:
        while True:
            message = await socket.receive()
            kind = message.get("type")
            if kind == "websocket.disconnect":
                break
            if message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except ValueError:
                    continue
                if isinstance(data, dict):
                    await session.on_client_message(data)
            elif message.get("bytes"):
                pcm = bytes(message["bytes"])
                if session.recorder is not None:
                    session.recorder.caller_audio(pcm, IN_RATE)
                if session.mode is CallMode.VOICE:
                    segmenter = segmenter or Segmenter()
                    started, segment = await segmenter.feed(pcm)
                    if started:
                        await session.caller_started_speaking()
                    if segment:
                        await session.caller_audio_segment(segment, IN_RATE)
            if session.engine.ended:
                break
    finally:
        session.send_json = None
        session.send_audio = None
