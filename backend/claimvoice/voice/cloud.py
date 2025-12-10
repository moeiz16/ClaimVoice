"""Cloud speech adapters behind the `SpeechToText` / `TextToSpeech` protocols, selected by STT_PROVIDER /
TTS_PROVIDER with a key. Nothing here runs offline: with no key the fakes are used.

| Provider | What | Endpoint |
|---|---|---|
| Groq | speech-to-text (Whisper large v3 turbo) | `POST /openai/v1/audio/transcriptions` (WAV upload) |
| Deepgram | speech-to-text (Nova 3) | `POST /v1/listen` (raw 16 kHz PCM) |
| Cartesia | text-to-speech (Sonic) | `POST /tts/bytes`, raw 24 kHz PCM, streamed |
| ElevenLabs | text-to-speech | `POST /v1/text-to-speech/{voice}/stream?output_format=pcm_24000`, streamed |

Each call has a timeout well inside the turn budget; a failure raises, and the session treats the turn as not
understood (one re-ask, then a person), so a provider outage never leaves the caller in silence.
"""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from claimvoice.voice.adapters import Language, Transcript

CHUNK = 960  # 20 ms at 24 kHz, 16-bit mono


def _wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@dataclass
class GroqWhisperSTT:
    api_key: str
    model: str = "whisper-large-v3-turbo"
    timeout_s: float = 2.0
    name: str = "groq-stt"

    async def transcribe(self, audio: bytes, *, sample_rate: int, language: Language | None) -> Transcript:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": self.model, "language": (language or "en")[:2], "response_format": "json"},
                files={"file": ("turn.wav", _wav(audio, sample_rate), "audio/wav")},
            )
            resp.raise_for_status()
            text = str(resp.json().get("text", "")).strip()
        return Transcript(text, (language or "en")[:2], 0.9 if text else 0.0)


@dataclass
class DeepgramSTT:
    api_key: str
    model: str = "nova-3"
    timeout_s: float = 2.0
    name: str = "deepgram-stt"

    async def transcribe(self, audio: bytes, *, sample_rate: int, language: Language | None) -> Transcript:
        lang = "fr-CA" if (language or "").startswith("fr") else "en-US"
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": self.model,
                    "language": lang,
                    "encoding": "linear16",
                    "sample_rate": sample_rate,
                    "smart_format": "true",
                },
                headers={"Authorization": f"Token {self.api_key}", "Content-Type": "audio/raw"},
                content=audio,
            )
            resp.raise_for_status()
            alt = resp.json()["results"]["channels"][0]["alternatives"][0]
        return Transcript(str(alt.get("transcript", "")), (language or "en")[:2], float(alt.get("confidence", 0.0)))


async def _stream(resp: httpx.Response) -> AsyncIterator[bytes]:
    pending = b""
    async for part in resp.aiter_bytes():
        pending += part
        while len(pending) >= CHUNK:
            yield pending[:CHUNK]
            pending = pending[CHUNK:]
    if pending:
        yield pending + b"\x00" * (CHUNK - len(pending))


@dataclass
class CartesiaTTS:
    api_key: str
    voices: dict[str, str]  # {"en": voice id, "fr": voice id}
    model: str = "sonic-2"
    sample_rate: int = 24000
    name: str = "cartesia-tts"

    async def synthesize(self, text: str, *, language: Language, voice: str | None = None) -> AsyncIterator[bytes]:
        body = {
            "model_id": self.model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice or self.voices.get(language[:2], self.voices.get("en", ""))},
            "language": language[:2],
            "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": self.sample_rate},
        }
        headers = {"X-API-Key": self.api_key, "Cartesia-Version": "2024-11-13"}
        async with (
            httpx.AsyncClient(timeout=5.0) as client,
            client.stream("POST", "https://api.cartesia.ai/tts/bytes", json=body, headers=headers) as resp,
        ):
            resp.raise_for_status()
            async for chunk in _stream(resp):
                yield chunk


@dataclass
class ElevenLabsTTS:
    api_key: str
    voices: dict[str, str]
    model: str = "eleven_flash_v2_5"
    sample_rate: int = 24000
    name: str = "elevenlabs-tts"

    async def synthesize(self, text: str, *, language: Language, voice: str | None = None) -> AsyncIterator[bytes]:
        vid = voice or self.voices.get(language[:2], self.voices.get("en", ""))
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream"
        async with (
            httpx.AsyncClient(timeout=5.0) as client,
            client.stream(
                "POST",
                url,
                params={"output_format": "pcm_24000"},
                json={"text": text, "model_id": self.model, "language_code": language[:2]},
                headers={"xi-api-key": self.api_key},
            ) as resp,
        ):
            resp.raise_for_status()
            async for chunk in _stream(resp):
                yield chunk
