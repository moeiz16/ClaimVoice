"""The read-back and the call summary, built only from values the caller gave (never improvised).

`read_back(values, language)` is what the line reads to the caller; `summary(...)` is the two-sentence version kept
on the call and the claim (`summary` in the call's language, `summary_en` for adjusters)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from claimvoice.dialogue.slots import LOSS_WORDS, display


def _join(parts: list[str], language: str) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    conj = " et " if language == "fr" else " and "
    return ", ".join(parts[:-1]) + conj + parts[-1]


def _when(v: Mapping[str, Any], language: str) -> str:
    out = []
    if v.get("loss_date"):
        out.append(("le " if language == "fr" else "on ") + display("loss_date", v["loss_date"], language))
    if v.get("loss_time"):
        out.append(display("loss_time", v["loss_time"], language))
    return ", ".join(out)


def facts(v: Mapping[str, Any], language: str) -> list[str]:
    fr = language == "fr"
    out: list[str] = []
    lt = v.get("loss_type")
    head = LOSS_WORDS.get(lt, {}).get(language, "") if lt else ""
    when = _when(v, language)
    if head:
        place = v.get("loss_place")
        loc = (f" ({place})" if place else "") if lt in ("collision", "theft") else ""
        out.append(f"{head}{loc} {when}".strip())
    if v.get("damage_areas") and lt != "collision":
        out.append(("dommages : " if fr else "damage to the ") + str(v["damage_areas"]))
    elif v.get("roof_or_window_damage"):
        out.append("toit ou fenêtres endommagés" if fr else "damage to the roof or windows")
    areas = str(v.get("damage_areas") or "")
    if v.get("siding_or_fence_damage") and not any(w in areas for w in ("siding", "fence", "revêtement", "clôture")):
        out.append("revêtement ou clôture endommagé" if fr else "siding or fence damaged")
    if v.get("debris_source"):
        out.append(("frappé par : " if fr else "hit by debris from ") + str(v["debris_source"]))
    if v.get("open_to_weather") is False and v.get("mitigation_taken"):
        out.append("l'ouverture est couverte" if fr else "the opening is now covered")
    elif v.get("open_to_weather") is True:
        out.append("encore ouvert aux intempéries" if fr else "still open to the weather")
    if v.get("water_source"):
        out.append(("source : " if fr else "from ") + display("water_source", v["water_source"], language))
    if v.get("rooms_affected"):
        n = int(v["rooms_affected"])
        out.append(
            f"{n} pièce{'s' if n > 1 else ''} touchée{'s' if n > 1 else ''}"
            if fr
            else f"{n} room{'s' if n > 1 else ''} affected"
        )
    if v.get("water_still_entering") is False:
        out.append("l'eau n'entre plus" if fr else "the water has stopped")
    elif v.get("water_still_entering") is True:
        out.append("l'eau entre encore" if fr else "water is still coming in")
    if lt == "collision":
        if v.get("other_party_involved"):
            ins = v.get("other_party_insurer")
            out.append(
                ("un autre véhicule en cause" + (f", assuré chez {ins}" if ins else ""))
                if fr
                else ("another vehicle involved" + (f", insured with {ins}" if ins else ""))
            )
        if v.get("police_report_filed"):
            num = v.get("police_report_number")
            out.append(("rapport de police " + (num or "")).strip() if fr else ("police report " + (num or "")).strip())
        if v.get("damage_areas"):
            out.append(("dommages : " if fr else "damage to the ") + str(v["damage_areas"]))
        if v.get("vehicle_drivable") is not None:
            out.append(
                ("le véhicule roule" if v["vehicle_drivable"] else "le véhicule ne roule pas")
                if fr
                else ("the vehicle can be driven" if v["vehicle_drivable"] else "the vehicle can't be driven")
            )
    if lt == "theft" and v.get("items_stolen"):
        out.append(("volé : " if fr else "taken: ") + str(v["items_stolen"]))
    if v.get("home_livable") is True:
        out.append("vous pouvez rester dans le logement" if fr else "you can stay in the home")
    elif v.get("home_livable") is False:
        out.append("vous ne pouvez pas rester dans le logement" if fr else "you can't stay in the home")
    if v.get("injury_reported") is True:
        detail = v.get("injury_detail")
        out.append(detail.lower() if detail else ("une blessure signalée" if fr else "an injury reported"))
    elif v.get("injury_reported") is False:
        out.append("personne n'est blessé" if fr else "nobody hurt")
    return out


def read_back(values: Mapping[str, Any], language: str) -> str:
    return _join(facts(values, language), language)


def summary(values: Mapping[str, Any], language: str, *, caller: str | None = None) -> str:
    body = read_back(values, language)
    if not body:
        return ""
    who = caller or ("L'appelant" if language == "fr" else "The caller")
    lead = f"{who} a signalé " if language == "fr" else f"{who} reported "
    text = lead + body + "."
    if values.get("photos_promised"):
        text += " Lien pour les photos envoyé." if language == "fr" else " Photo link sent."
    return text
