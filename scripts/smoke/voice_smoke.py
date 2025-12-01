"""Voice toolchain smoke: Pipecat SmallWebRTC loopback + Silero VAD, fully offline.

What it proves on this machine (Python 3.13):
1. Pipecat's SmallWebRTCConnection answers an SDP offer from a plain aiortc peer (no media server, no STUN).
2. A Pipecat pipeline (transport.input -> echo -> transport.output) receives a JSON message from the browser side over
   the WebRTC data channel and sends one back. This is the path the offline demo uses: the browser's own speech
   recognition turns speech into text and sends it as `caller.text`, and the reply comes back as `agent.text`.
3. An audio track from the client reaches the server (the cloud speech-to-text path).
4. Silero VAD (bundled ONNX model, onnxruntime on CPU) scores 16 kHz audio and reports its per-chunk cost.

Run: backend/.venv/bin/python scripts/smoke/voice_smoke.py
"""

from __future__ import annotations

import asyncio
import contextlib
import fractions
import json
import math
import resource
import sys
import time

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import AudioFrame
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, InputAudioRawFrame, InputTransportMessageFrame, OutputTransportMessageFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

SAMPLE_RATE = 16000


class ToneTrack(AudioStreamTrack):
    """A 440 Hz tone in 20 ms frames, standing in for a microphone."""

    def __init__(self) -> None:
        super().__init__()
        self._pts = 0

    async def recv(self) -> AudioFrame:
        samples = 960  # 20 ms at 48 kHz
        await asyncio.sleep(0.02)
        t = (np.arange(samples) + self._pts) / 48000
        pcm = (np.sin(2 * math.pi * 440 * t) * 8000).astype(np.int16).reshape(1, -1)
        frame = AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.sample_rate = 48000
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, 48000)
        self._pts += samples
        return frame


class Echo(FrameProcessor):
    """Replies to every data-channel message and counts audio frames."""

    def __init__(self) -> None:
        super().__init__()
        self.audio_frames = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, InputTransportMessageFrame):
            msg = frame.message
            if isinstance(msg, dict) and msg.get("type") == "caller.text":
                reply = {"type": "agent.text", "text": f"I heard: {msg.get('text', '')}"}
                await self.push_frame(OutputTransportMessageFrame(message=reply))
            return
        if isinstance(frame, InputAudioRawFrame):
            self.audio_frames += 1
        await self.push_frame(frame, direction)


async def webrtc_loopback() -> dict:
    server = SmallWebRTCConnection(ice_servers=[])
    transport = SmallWebRTCTransport(
        webrtc_connection=server,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True, audio_in_sample_rate=SAMPLE_RATE),
    )
    echo = Echo()
    worker = PipelineWorker(
        Pipeline([transport.input(), echo, transport.output()]),
        params=PipelineParams(audio_in_sample_rate=SAMPLE_RATE, audio_out_sample_rate=24000),
        enable_rtvi=False,
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    run = asyncio.create_task(runner.run())

    client = RTCPeerConnection()
    client.addTrack(ToneTrack())
    channel = client.createDataChannel("chat")
    replies: asyncio.Queue[dict] = asyncio.Queue()

    @channel.on("message")
    def on_message(message: str) -> None:
        if not message.startswith("ping"):
            replies.put_nowait(json.loads(message))

    opened = asyncio.Event()
    channel.on("open", opened.set)

    t0 = time.perf_counter()
    await client.setLocalDescription(await client.createOffer())
    await server.initialize(sdp=client.localDescription.sdp, type=client.localDescription.type)
    await server.connect()
    answer = server.get_answer()
    await client.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    await asyncio.wait_for(opened.wait(), 15)
    connect_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    channel.send(json.dumps({"type": "caller.text", "text": "my basement is flooded"}))
    reply = await asyncio.wait_for(replies.get(), 10)
    rtt_ms = (time.perf_counter() - t1) * 1000

    await asyncio.sleep(1.0)  # let some audio arrive
    audio_frames = echo.audio_frames

    await runner.cancel()
    await client.close()
    await server.disconnect()
    run.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run
    return {"connect_ms": round(connect_ms), "rtt_ms": round(rtt_ms, 1), "reply": reply, "audio_frames": audio_frames}


async def vad_check() -> dict:
    vad = SileroVADAnalyzer()
    vad.set_sample_rate(SAMPLE_RATE)
    chunk = vad.num_frames_required()
    silence = np.zeros(chunk, dtype=np.int16).tobytes()
    rng = np.random.default_rng(7)
    noise = (rng.normal(0, 3000, chunk)).astype(np.int16).tobytes()
    t = time.perf_counter()
    n = 200
    for i in range(n):
        vad.voice_confidence(silence if i % 2 else noise)
    per_chunk_ms = (time.perf_counter() - t) * 1000 / n
    return {
        "chunk_samples": chunk,
        "silence_confidence": round(float(np.asarray(vad.voice_confidence(silence)).ravel()[0]), 3),
        "ms_per_chunk": round(per_chunk_ms, 3),
    }


async def main() -> int:
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    loop = await webrtc_loopback()
    vad = await vad_check()
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    print(json.dumps({"webrtc": loop, "vad": vad, "peak_rss_mb": round(peak_mb)}, indent=2))
    ok = loop["reply"].get("type") == "agent.text" and loop["audio_frames"] > 0 and vad["silence_confidence"] < 0.5
    print("voice smoke:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
