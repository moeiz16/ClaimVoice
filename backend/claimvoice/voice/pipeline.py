"""The Pipecat pipeline for one browser call over SmallWebRTC (docs/adr/0002).

    transport.input() -> VADProcessor(Silero) -> CallProcessor -> transport.output()

* JSON messages on the "claimvoice" data channel arrive as `InputTransportMessageFrame`s and go to the call session;
  replies go back over the same channel. The browser's `ping-<ms>` keep-alive is handled by the connection itself
  (a gap over 3 s marks the caller as disconnected; the line manager ends the call after 30 s without the caller).
* The microphone track arrives as `InputAudioRawFrame`s at 16 kHz: always recorded once the caller agrees, and in
  `voice` mode cut by Silero VAD into segments for speech-to-text.
* Barge-in: when the VAD hears the caller start while the line is speaking, the processor interrupts the pipeline
  (flushing queued line audio) and the session cancels synthesis and sends `line.stop`.
* Line audio (`voice` mode) is pushed as `OutputAudioRawFrame`s at 24 kHz; the transport paces it.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import structlog
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InputTransportMessageFrame,
    OutputAudioRawFrame,
    StartFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from claimvoice.contracts import CallMode
from claimvoice.voice.session import CallSession

log = structlog.get_logger("claimvoice.voice")
IN_RATE = 16000
OUT_RATE = 24000


def vad_analyzer() -> SileroVADAnalyzer:
    return SileroVADAnalyzer(params=VADParams(stop_secs=0.2, start_secs=0.2, confidence=0.7))


class CallProcessor(FrameProcessor):
    """Bridges Pipecat frames and the call session."""

    def __init__(self, session: CallSession) -> None:
        super().__init__()
        self.session = session
        self._segment = bytearray()
        self._in_speech = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        s = self.session
        if isinstance(frame, InputTransportMessageFrame):
            msg = frame.message
            if isinstance(msg, dict):
                asyncio.create_task(s.on_client_message(msg))  # noqa: RUF006 - kept by the session lock
            return
        if isinstance(frame, InputAudioRawFrame):
            if s.recorder is not None:
                s.recorder.caller_audio(frame.audio, frame.sample_rate)
            if self._in_speech and s.mode is CallMode.VOICE:
                self._segment.extend(frame.audio)
            return
        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._in_speech = True
            self._segment.clear()
            if s.speaking_turn is not None and s.mode is CallMode.VOICE:
                await self.broadcast_interruption()  # flush the line's queued audio now
            await s.caller_started_speaking()
            return
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            self._in_speech = False
            if s.mode is CallMode.VOICE and self._segment:
                pcm = bytes(self._segment)
                self._segment.clear()
                asyncio.create_task(s.caller_audio_segment(pcm, IN_RATE))  # noqa: RUF006
            return
        await self.push_frame(frame, direction)

    async def send_audio(self, pcm: bytes) -> None:
        await self.push_frame(OutputAudioRawFrame(audio=pcm, sample_rate=OUT_RATE, num_channels=1))


class WebRtcLeg:
    """One SmallWebRTC peer connection and the pipeline that serves it."""

    def __init__(self, session: CallSession, ice_servers: list[str]) -> None:
        self.session = session
        self.connection = SmallWebRTCConnection(ice_servers=ice_servers or [])
        self.processor = CallProcessor(session)
        self.runner: WorkerRunner | None = None
        self.task: asyncio.Task[Any] | None = None

    async def answer(self, sdp: str, type_: str) -> dict[str, Any]:
        await self.connection.initialize(sdp=sdp, type=type_)
        voice = self.session.mode is CallMode.VOICE
        transport = SmallWebRTCTransport(
            webrtc_connection=self.connection,
            params=TransportParams(
                audio_in_enabled=True,
                audio_in_sample_rate=IN_RATE,
                audio_out_enabled=voice,
                audio_out_sample_rate=OUT_RATE,
            ),
        )
        worker = PipelineWorker(
            Pipeline(
                [transport.input(), VADProcessor(vad_analyzer=vad_analyzer()), self.processor, transport.output()]
            ),
            params=PipelineParams(audio_in_sample_rate=IN_RATE, audio_out_sample_rate=OUT_RATE),
            enable_rtvi=False,
        )
        self.runner = WorkerRunner(handle_sigint=False)
        await self.runner.add_workers(worker)
        self.task = asyncio.create_task(self.runner.run())

        async def send_json(msg: dict[str, Any]) -> None:
            self.connection.send_app_message(msg)

        self.session.send_json = send_json
        if voice:
            self.session.send_audio = self.processor.send_audio
        await self.connection.connect()
        answer = self.connection.get_answer()
        return {"sdp": answer["sdp"], "type": answer["type"], "pcId": answer["pc_id"]}

    async def renegotiate(self, sdp: str, type_: str, restart_pc: bool) -> dict[str, Any]:
        await self.connection.renegotiate(sdp=sdp, type=type_, restart_pc=restart_pc)
        answer = self.connection.get_answer()
        return {"sdp": answer["sdp"], "type": answer["type"], "pcId": answer["pc_id"]}

    async def add_ice(self, candidates: list[dict[str, Any]]) -> None:
        from aiortc.sdp import candidate_from_sdp

        for c in candidates:
            raw = str(c.get("candidate") or "")
            if not raw:
                continue
            cand = candidate_from_sdp(raw.split(":", 1)[1] if raw.startswith("candidate:") else raw)
            cand.sdpMid = c.get("sdpMid")
            cand.sdpMLineIndex = c.get("sdpMLineIndex")
            await self.connection.add_ice_candidate(cand)

    def connected(self) -> bool:
        try:
            return bool(self.connection.is_connected())
        except Exception:
            return False

    @property
    def pc_id(self) -> str:
        return str(self.connection.pc_id)

    async def close(self) -> None:
        if self.runner is not None:
            with contextlib.suppress(Exception):
                await self.runner.cancel()
        with contextlib.suppress(Exception):
            await self.connection.disconnect()
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.task


__all__ = ["CallProcessor", "CancelFrame", "EndFrame", "StartFrame", "WebRtcLeg", "vad_analyzer"]
