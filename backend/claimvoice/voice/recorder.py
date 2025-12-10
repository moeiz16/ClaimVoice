"""Call recordings: stereo 16 kHz WAV, the caller on the left channel and Larkspur's side (the line, or a person) on
the right, so the recording band can draw two lanes.

Nothing is written until the caller agrees to recording; in all-party regions audio before the yes stays in memory
and is dropped if the answer is no. Card-number moments are silenced on both channels before the file is written
(there is nothing to "unhide"). In `browser_speech` mode the line's voice is produced by the browser, so the right
channel is silence where the line spoke; captions carry its words."""

from __future__ import annotations

import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

RATE = 16000


def _resample(pcm: bytes, rate: int) -> np.ndarray:
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    if rate == RATE or len(x) == 0:
        return x
    n = int(len(x) * RATE / rate)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


@dataclass
class Recorder:
    call_id: str
    directory: Path
    started: float = 0.0
    recording: bool = False  # follows consent
    left: list[np.ndarray] = field(default_factory=list)
    right: list[np.ndarray] = field(default_factory=list)
    hushes: list[tuple[int, int]] = field(default_factory=list)
    _left_n: int = 0
    _right_n: int = 0
    refused: bool = False

    def caller_audio(self, pcm: bytes, rate: int) -> None:
        if self.refused:
            return
        x = _resample(pcm, rate)
        self.left.append(x)
        self._left_n += len(x)
        self._pad_right()

    def line_audio(self, pcm: bytes, rate: int) -> None:
        if self.refused:
            return
        x = _resample(pcm, rate)
        if self._right_n < self._left_n:  # line audio starts now, after the caller's audio so far
            self.right.append(np.zeros(self._left_n - self._right_n, dtype=np.float32))
            self._right_n = self._left_n
        self.right.append(x)
        self._right_n += len(x)

    def _pad_right(self) -> None:
        pass  # the right channel catches up lazily (silence) when the line next speaks or at the end

    def hush(self, start_ms: int, end_ms: int) -> None:
        self.hushes.append((start_ms, end_ms))

    def refuse(self) -> None:
        """The caller said no to recording: drop everything and keep nothing more."""
        self.refused = True
        self.left.clear()
        self.right.clear()

    def finish(self) -> tuple[str | None, float | None]:
        if not self.recording or self.refused or not (self.left or self.right):
            return None, None
        left = np.concatenate(self.left) if self.left else np.zeros(0, np.float32)
        right = np.concatenate(self.right) if self.right else np.zeros(0, np.float32)
        n = max(len(left), len(right))
        left = np.pad(left, (0, n - len(left)))
        right = np.pad(right, (0, n - len(right)))
        for a, b in self.hushes:
            i, j = max(0, a * RATE // 1000), min(n, b * RATE // 1000)
            left[i:j] = 0
            right[i:j] = 0
        stereo = np.stack([left, right], axis=1).clip(-32768, 32767).astype("<i2")
        self.directory.mkdir(parents=True, exist_ok=True)
        name = f"{self.call_id}.wav"
        with wave.open(str(self.directory / name), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(stereo.tobytes())
        return name, round(n / RATE, 2)
