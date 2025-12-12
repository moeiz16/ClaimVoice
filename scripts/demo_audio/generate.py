"""Generate the landing page's recorded call (English and French) with macOS `say` system voices.

Run once on a Mac (needs `say` and the backend venv for PyAV and NumPy):

    backend/.venv/bin/python scripts/demo_audio/generate.py

Writes to frontend/public/audio/:
* `dana-call.ogg` / `dana-call-fr.ogg`: Opus, mono, 24 kHz, about 24 kbit/s;
* `dana-call.m4a` / `dana-call-fr.m4a`: AAC, for Safari;
* `dana-call.json` / `dana-call-fr.json`: the timed transcript for captions: turns with `from`/`to` seconds, the
  heard spans (exact substrings), the card-number cut (`hush`), the moments, the claim slip, the route reveal and
  waveform peaks for each lane.

The card digits are never in the audio: the caller's turn is rendered up to "It's", then silence, exactly as the line
removes card numbers before anything is kept. Voices are synthetic; the page says so.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("dana_call.yml")
OUT = ROOT / "frontend" / "public" / "audio"
RATE = 24000
GAP = {("cv", "caller"): 0.45, ("caller", "cv"): 0.4, ("cv", "cv"): 0.3, ("caller", "caller"): 0.3}
PEAKS = 400


def say(text: str, voice: str, rate: int, tmp: Path) -> np.ndarray:
    path = tmp / "t.wav"
    subprocess.run(  # noqa: S603 - fixed binary, our own text
        [
            "/usr/bin/say",
            "-v",
            voice,
            "-r",
            str(rate),
            "-o",
            str(path),
            "--file-format=WAVE",
            f"--data-format=LEI16@{RATE}",
            text,
        ],
        check=True,
    )
    with wave.open(str(path), "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    nz = np.nonzero(np.abs(pcm) > 200)[0]  # trim the synthesiser's leading and trailing silence
    return pcm[max(0, nz[0] - 240) : nz[-1] + 480] if len(nz) else pcm


def encode(pcm: np.ndarray, path: Path, codec: str, bitrate: int) -> None:
    import av

    container = av.open(str(path), "w")
    stream = container.add_stream(codec, rate=RATE)
    stream.bit_rate = bitrate
    stream.layout = "mono"
    samples = pcm.clip(-32768, 32767).astype("<i2")
    step = 960
    for i in range(0, len(samples), step):
        chunk = samples[i : i + step]
        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = RATE
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()


def peaks(lane: np.ndarray, n: int = PEAKS) -> list[float]:
    windows = np.array_split(np.abs(lane), n)
    top = max(1.0, float(np.max(np.abs(lane))))
    return [round(float(w.max()) / top, 3) if len(w) else 0.0 for w in windows]


def build(lang: str, doc: dict[str, Any], tmp: Path) -> dict[str, Any]:
    voices = doc["voices"][lang]
    audio: list[np.ndarray] = []
    lanes = {"cv": [], "caller": []}
    turns_out = []
    t = 0.0
    prev = None
    for raw in doc["turns"][lang]:
        who = raw["who"]
        if prev is not None:
            gap = np.zeros(int(GAP[(prev, who)] * RATE), np.float32)
            audio.append(gap)
            for k in lanes:
                lanes[k].append(gap)
            t += len(gap) / RATE
        voice = voices["cv"] if who == "cv" else voices["caller"]
        rate = voices["rate_cv"] if who == "cv" else voices["rate_caller"]
        hush_at: float | None = None
        if raw.get("hush_from"):
            head = raw["text"].split(raw["hush_from"])[0] + raw["hush_from"]
            spoken = say(head, voice, rate, tmp)
            hush_at = t + len(spoken) / RATE
            silence = np.zeros(int(1.3 * RATE), np.float32)  # where the digits were: removed, never recorded
            pcm = np.concatenate([spoken, silence])
            text = head + " [card number removed]"
        else:
            pcm = say(raw["text"], voice, rate, tmp)
            text = raw.get("display", raw["text"])
        start, end = t, t + len(pcm) / RATE
        audio.append(pcm)
        lanes[who].append(pcm)
        lanes["caller" if who == "cv" else "cv"].append(np.zeros(len(pcm), np.float32))
        spans = [{"text": s, "key": k} for s, k in raw.get("spans", []) if s in text]
        missing = [s for s, _ in raw.get("spans", []) if s not in text]
        if missing:
            raise ValueError(f"span not in turn text: {missing}")
        turn = {"who": who, "from": round(start, 2), "to": round(end, 2), "text": text, "spans": spans}
        if hush_at is not None:
            turn["hush"] = round(hush_at, 2)
        turns_out.append(turn)
        t = end
        prev = who
    full = np.concatenate(audio)
    first_at: dict[str, float] = {}
    for turn in turns_out:
        for s in turn["spans"]:
            first_at.setdefault(s["key"], turn["from"])
        if "hush" in turn:
            first_at.setdefault("card", turn["hush"])
    route = doc["route"]
    return {
        "pcm": full,
        "doc": {
            "claimNumber": doc["claim_number"],
            "language": lang,
            "durationSeconds": round(len(full) / RATE, 2),
            "sample": "Sample call, voices are synthetic",
            "turns": turns_out,
            "moments": [{"key": m["key"], "label": m[lang], "at": first_at.get(m["key"])} for m in doc["moments"]],
            "slip": [
                {
                    "key": s["key"],
                    "label": s[lang],
                    "at": first_at.get(s["at_span"]),
                    **({"hushed": True} if s.get("hushed") else {}),
                }
                for s in doc["slip"]
            ],
            "route": {
                "route": route["route"],
                "label": route["label"][lang],
                "reasons": [{"text": r[lang], "atSeconds": first_at.get(r["key"])} for r in route["reasons"]],
            },
            "peaks": {"cv": peaks(np.concatenate(lanes["cv"])), "caller": peaks(np.concatenate(lanes["caller"]))},
        },
    }


def main() -> int:
    if sys.platform != "darwin":
        print("This needs macOS `say`.")
        return 1
    doc = yaml.safe_load(SCRIPT.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for lang, suffix in (("en", ""), ("fr", "-fr")):
            built = build(lang, doc, Path(tmp))
            base = OUT / f"dana-call{suffix}"
            encode(built["pcm"], base.with_suffix(".ogg"), "libopus", 24000)
            encode(built["pcm"], base.with_suffix(".m4a"), "aac", 32000)
            base.with_suffix(".json").write_text(json.dumps(built["doc"], ensure_ascii=False, indent=1) + "\n")
            print(lang, built["doc"]["durationSeconds"], "s")
    total = sum(p.stat().st_size for p in OUT.glob("dana-call*"))
    print(f"total {total / 1024:.0f} KB")
    return 0 if total <= 2 * 1024 * 1024 else 1


if __name__ == "__main__":
    sys.exit(main())
