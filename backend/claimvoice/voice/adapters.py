"""Speech adapters: speech-to-text and text-to-speech, each a Protocol with an offline deterministic fake.

Cloud implementations (Groq Whisper, Deepgram, Cartesia) wrap Pipecat's service classes behind the same Protocols and
are selected by STT_PROVIDER / TTS_PROVIDER; with no key the fakes are used. Audio is 16-bit little-endian mono PCM.
"""

from __future__ import annotations

import math
import struct
from collections import deque
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

Language = str  # "en" | "fr" (BCP-47 region variants such as "fr-CA" are accepted and reduced to the base)


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: Language
    confidence: float  # 0..1
    is_final: bool = True
    words: tuple[tuple[str, int, int], ...] = ()  # (word, start_ms, end_ms) when the service provides them


@runtime_checkable
class SpeechToText(Protocol):
    name: str

    async def transcribe(self, audio: bytes, *, sample_rate: int, language: Language | None) -> Transcript:
        """Transcribe one VAD-bounded caller segment. Must honour the caller's language when given."""
        ...


@runtime_checkable
class TextToSpeech(Protocol):
    name: str
    sample_rate: int

    def synthesize(self, text: str, *, language: Language, voice: str | None = None) -> AsyncIterator[bytes]:
        """Yield PCM chunks (20 ms each) as soon as they are ready; the first chunk's delay is the time to first audio.
        Cancellation (barge-in) is by closing the iterator."""
        ...


@dataclass
class FakeSpeechToText:
    """Deterministic STT for tests, evals and latency runs: returns scripted lines in order.

    Scripted callers (eval/callers/*.yml) queue the caller's next line; when the queue is empty the fake returns an
    empty, low-confidence transcript (what a real service returns for noise)."""

    name: str = "fake-stt"
    script: deque[Transcript] = field(default_factory=deque)

    def queue(self, lines: Iterable[str], *, language: Language = "en", confidence: float = 0.95) -> None:
        for line in lines:
            self.script.append(Transcript(line, language, confidence))

    async def transcribe(self, audio: bytes, *, sample_rate: int, language: Language | None) -> Transcript:
        if self.script:
            return self.script.popleft()
        return Transcript("", (language or "en")[:2], 0.0)


@dataclass
class FakeTextToSpeech:
    """Deterministic TTS: a quiet 220 Hz tone, 55 ms per character up to 12 s, in 20 ms chunks, no network.

    Gives the recording real duration and the latency harness a real first-chunk time; the words themselves travel
    as captions (`line.say`)."""

    name: str = "fake-tts"
    sample_rate: int = 24000
    ms_per_char: int = 55
    max_ms: int = 12000

    async def synthesize(self, text: str, *, language: Language, voice: str | None = None) -> AsyncIterator[bytes]:
        total_ms = min(self.max_ms, max(200, len(text) * self.ms_per_char))
        per_chunk = self.sample_rate // 50  # 20 ms
        for chunk_index in range(total_ms // 20):
            base = chunk_index * per_chunk
            samples = (int(600 * math.sin(2 * math.pi * 220 * (base + i) / self.sample_rate)) for i in range(per_chunk))
            yield struct.pack(f"<{per_chunk}h", *samples)


def get_speech_adapters() -> tuple[SpeechToText, TextToSpeech]:
    """The configured speech services: fakes unless STT_PROVIDER / TTS_PROVIDER name a provider and its key is set.
    Voices for cloud speech come from CARTESIA_VOICE_EN/FR or ELEVENLABS_VOICE_EN/FR."""
    import os

    from claimvoice.config import get_settings

    s = get_settings()
    stt: SpeechToText = FakeSpeechToText()
    tts: TextToSpeech = FakeTextToSpeech()
    stt_provider = os.environ.get("STT_PROVIDER", s.stt_provider)
    tts_provider = os.environ.get("TTS_PROVIDER", s.tts_provider)
    if stt_provider == "groq" and s.groq_api_key:
        from claimvoice.voice.cloud import GroqWhisperSTT

        stt = GroqWhisperSTT(s.groq_api_key)
    elif stt_provider == "deepgram" and s.deepgram_api_key:
        from claimvoice.voice.cloud import DeepgramSTT

        stt = DeepgramSTT(s.deepgram_api_key)
    if tts_provider == "cartesia" and s.cartesia_api_key:
        from claimvoice.voice.cloud import CartesiaTTS

        tts = CartesiaTTS(
            s.cartesia_api_key,
            {"en": s.cartesia_voice_en, "fr": s.cartesia_voice_fr},
        )
    elif tts_provider == "elevenlabs" and s.elevenlabs_api_key:
        from claimvoice.voice.cloud import ElevenLabsTTS

        tts = ElevenLabsTTS(
            s.elevenlabs_api_key,
            {"en": s.elevenlabs_voice_en, "fr": s.elevenlabs_voice_fr},
        )
    return stt, tts
