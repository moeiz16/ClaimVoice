"""A plain aiortc peer standing in for the browser (offer, data channel, `ping-<ms>` keep-alive, microphone)."""

from __future__ import annotations

import asyncio
import contextlib
import fractions
import json
import math
import time
from typing import Any

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import AudioFrame


class ToneTrack(AudioStreamTrack):
    def __init__(self) -> None:
        super().__init__()
        self._pts = 0

    async def recv(self) -> AudioFrame:
        samples = 960
        await asyncio.sleep(0.02)
        t = (np.arange(samples) + self._pts) / 48000
        pcm = (np.sin(2 * math.pi * 330 * t) * 3000).astype(np.int16).reshape(1, -1)
        frame = AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.sample_rate = 48000
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, 48000)
        self._pts += samples
        return frame


class BrowserPeer:
    def __init__(self, *, microphone: bool = True) -> None:
        self.pc = RTCPeerConnection()
        if microphone:
            self.pc.addTrack(ToneTrack())
        self.channel = self.pc.createDataChannel("claimvoice")
        self.inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.opened = asyncio.Event()
        self.channel.on("open", self.opened.set)

        @self.channel.on("message")
        def _on(message: str) -> None:
            if isinstance(message, str) and not message.startswith("ping"):
                self.inbox.put_nowait(json.loads(message))

        self._ping: asyncio.Task[None] | None = None

    async def offer(self) -> tuple[str, str]:
        await self.pc.setLocalDescription(await self.pc.createOffer())
        return self.pc.localDescription.sdp, self.pc.localDescription.type

    async def accept(self, answer: dict[str, Any]) -> None:
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
        await asyncio.wait_for(self.opened.wait(), 15)
        self._ping = asyncio.create_task(self._keepalive())

    async def _keepalive(self) -> None:
        while True:
            self.channel.send(f"ping-{int(time.time() * 1000)}")
            await asyncio.sleep(1)

    def send(self, msg: dict[str, Any]) -> None:
        self.channel.send(json.dumps(msg))

    async def until(self, kind: str, wait: float = 10.0, **match: Any) -> dict[str, Any]:
        deadline = time.monotonic() + wait
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError(kind)
            msg = await asyncio.wait_for(self.inbox.get(), left)
            if msg.get("type") == kind and all(msg.get(k) == v for k, v in match.items()):
                return msg

    async def close(self) -> None:
        if self._ping is not None:
            self._ping.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ping
        await self.pc.close()
