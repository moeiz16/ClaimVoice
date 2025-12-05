"""Serving a call's recording with HTTP Range support.

Live calls write `RECORDINGS_DIR/{call_id}.ogg` (or `.wav`). Seeded calls have no audio of their own, so the first
play renders a small placeholder track from the turn timing (8 kHz mono: a soft murmur where someone spoke, silence
in the gaps and the card-number cuts) and caches it next to the real recordings. The UI labels sample calls."""

from __future__ import annotations

import hashlib
import io
import math
import struct
import wave
from collections.abc import Sequence
from pathlib import Path

from litestar import Response

from claimvoice.calls.models import Call, CallTurn
from claimvoice.config import get_settings
from claimvoice.platform.errors import ProblemError

RATE = 8000
CHUNK_MAX = 1024 * 1024


def recording_file(call: Call) -> Path | None:
    base = get_settings().recordings_dir
    if call.recording_path:
        path = (base / call.recording_path).resolve()
        if base.resolve() in path.parents and path.is_file():
            return path
    cached = base / "sample" / f"{call.id}.wav"
    return cached if cached.is_file() else None


def render_placeholder(call: Call, turns: Sequence[CallTurn], duration_s: float) -> Path:
    base = get_settings().recordings_dir / "sample"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{call.id}.wav"
    n = int(duration_s * RATE)
    frames = bytearray(n * 2)
    for t in turns:
        if t.speaker not in ("caller", "line", "person") or t.redactions:
            continue
        a, b = int(t.at_ms / 1000 * RATE), min(n, int(t.end_ms / 1000 * RATE))
        seed = int.from_bytes(hashlib.sha256(t.id.encode()).digest()[:4], "big")
        freq = 150.0 if t.speaker == "caller" else 210.0
        amp = 900 if t.speaker == "caller" else 700
        for i in range(a, b):
            syll = 0.5 + 0.5 * math.sin(2 * math.pi * 3.1 * (i - a) / RATE + seed % 7)
            v = int(amp * syll * math.sin(2 * math.pi * freq * i / RATE))
            struct.pack_into("<h", frames, i * 2, v)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(path)
    return path


def ranged(path: Path, range_header: str | None) -> Response[bytes]:
    size = path.stat().st_size
    media = "audio/ogg" if path.suffix == ".ogg" else "audio/wav"
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, no-store"}
    if not range_header or not range_header.startswith("bytes="):
        return Response(path.read_bytes(), media_type=media, headers=headers)
    spec = range_header[len("bytes=") :].split(",")[0].strip()
    start_s, _, end_s = spec.partition("-")
    try:
        if start_s:
            start = int(start_s)
            end = int(end_s) if end_s else min(size - 1, start + CHUNK_MAX - 1)
        else:
            length = int(end_s)
            start, end = max(0, size - length), size - 1
    except ValueError as exc:
        raise ProblemError(400, "bad_request", "Bad range") from exc
    if start >= size or start > end:
        return Response(b"", status_code=416, media_type=media, headers={**headers, "Content-Range": f"bytes */{size}"})
    end = min(end, size - 1)
    with path.open("rb") as f:
        f.seek(start)
        body = f.read(end - start + 1)
    return Response(
        body, status_code=206, media_type=media, headers={**headers, "Content-Range": f"bytes {start}-{end}/{size}"}
    )
