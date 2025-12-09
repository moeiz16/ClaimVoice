"""Shared shapes for the evaluation suites."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
ROOT = EVAL.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@dataclass(frozen=True)
class Gate:
    suite: str
    key: str
    label: str
    value: float
    limit: float
    direction: str  # "min" (value >= limit passes) or "max" (value <= limit passes)

    @property
    def passed(self) -> bool:
        return self.value >= self.limit if self.direction == "min" else self.value <= self.limit


@dataclass
class Report:
    gates: list[Gate] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)  # Markdown details for RESULTS.md (no timestamps)
    data: dict[str, object] = field(default_factory=dict)  # machine-readable numbers for results.json


def table(headers: list[str], rows: list[list[object]], align: str | None = None) -> list[str]:
    align = align or "|".join("---" if i == 0 else "---:" for i in range(len(headers)))
    out = ["| " + " | ".join(headers) + " |", "|" + align + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out
