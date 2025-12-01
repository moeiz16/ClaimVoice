"""Download freMTPL2 (French motor third-party liability) from OpenML into data/fremtpl2/.

freMTPL2freq (OpenML 41214, 677,991 policies) and freMTPL2sev (OpenML 41215, 26,639 claim amounts), as Parquet
(~7.7 MB transferred). Checksums are pinned in scripts/data_pins.json after the first verified download, so a changed
upstream file is noticed rather than silently used. Idempotent: existing files with the right checksum are kept.

Run: make data  (or backend/.venv/bin/python scripts/fetch_data.py)
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "fremtpl2"
PINS = ROOT / "scripts" / "data_pins.json"

SOURCES = {
    "freMTPL2freq.parquet": "https://data.openml.org/datasets/0004/41214/dataset_41214.pq",
    "freMTPL2sev.parquet": "https://data.openml.org/datasets/0004/41215/dataset_41215.pq",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    pins: dict[str, str] = json.loads(PINS.read_text()) if PINS.exists() else {}
    changed = False
    for name, url in SOURCES.items():
        target = DEST / name
        if target.exists() and pins.get(name) == sha256(target):
            print(f"ok      {name} (cached)")
            continue
        print(f"fetch   {name} <- {url}")
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        digest = sha256(tmp)
        if name in pins and pins[name] != digest:
            tmp.unlink()
            print(f"error   {name}: checksum {digest} does not match the pin {pins[name]}", file=sys.stderr)
            return 1
        tmp.replace(target)
        if name not in pins:
            pins[name] = digest
            changed = True
        print(f"ok      {name} ({target.stat().st_size / 1e6:.1f} MB)")
    if changed:
        PINS.write_text(json.dumps(pins, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
