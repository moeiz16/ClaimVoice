"""Default call scripts, one bilingual YAML file per loss type. The platform seeds them into the `scripts` table
(Settings › Scripts); a live call keeps the version it started with.

YAML shape (per file): `loss_type`, `line`, `version`, and `questions: [{slot_key, kind, label{en,fr},
prompt{en,fr}, required, when, choices, surge_only}]`. `when` is a simple condition on filled values:
`key == true`, `key == false`, `key != value`, `key >= 3`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from claimvoice.contracts import Script, ScriptQuestion

SCRIPTS_DIR = Path(__file__).parent
_COND = re.compile(r"^\s*(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


def _question(raw: Mapping[str, Any]) -> ScriptQuestion:
    return ScriptQuestion(
        slot_key=raw["slot_key"],
        kind=raw.get("kind", "text"),
        prompt=dict(raw["prompt"]),
        required=bool(raw.get("required", True)),
        when=raw.get("when"),
        choices=tuple(raw.get("choices") or ()),
        label=dict(raw.get("label") or {}),
        surge_only=bool(raw.get("surge_only", False)),
    )


def script_from_dict(raw: Mapping[str, Any]) -> Script:
    return Script(
        loss_type=raw["loss_type"],
        version=int(raw.get("version", 1)),
        questions=tuple(_question(q) for q in raw["questions"]),
    )


@cache
def load_default_scripts() -> dict[str, Script]:
    out: dict[str, Script] = {}
    for path in sorted(SCRIPTS_DIR.glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[raw["loss_type"]] = script_from_dict(raw)
    return out


def raw_default_scripts() -> dict[str, dict[str, Any]]:
    """The YAML as dictionaries (for seeding the `scripts` table with labels and the line)."""
    return {
        (raw := yaml.safe_load(p.read_text(encoding="utf-8")))["loss_type"]: raw
        for p in sorted(SCRIPTS_DIR.glob("*.yml"))
    }


def _literal(text: str) -> Any:
    t = text.strip().strip("'\"")
    if t.lower() == "true":
        return True
    if t.lower() == "false":
        return False
    try:
        return float(t)
    except ValueError:
        return t


def condition_holds(when: str | None, filled: Mapping[str, Any]) -> bool:
    """True when the question applies. Unknown values make an equality condition false (we don't ask yet)."""
    if not when:
        return True
    m = _COND.match(when)
    if not m:
        return True
    key, op, raw = m.groups()
    have = filled.get(key)
    want = _literal(raw)
    if have is None:
        return op == "!="
    if op == "==":
        return bool(have == want)
    if op == "!=":
        return bool(have != want)
    try:
        h, w = float(have), float(want)
    except (TypeError, ValueError):
        return False
    return {">=": h >= w, "<=": h <= w, ">": h > w, "<": h < w}[op]
