"""Routing rules shared by training, the fairness check and the live scorer (docs/API_CONTRACT.md §6.1).

The models produce calibrated probabilities; fixed rules always win:

1. urgent safety on the call -> adjuster (priority), whatever the scores;
2. a possible injury is never fast-tracked;
3. closer-look probability >= threshold **and** at least 2 signs present -> special investigation (a request for a
   person to review, never a denial);
4. size probability >= threshold, water still coming in, or the home open to the weather -> adjuster;
5. otherwise fast-track.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from claimvoice.ml.features import signs_present

RULE_TEXT: dict[str, dict[str, str]] = {
    "urgent": {
        "en": "Urgent safety on the call: an adjuster, first in line",
        "fr": "Urgence de sécurité pendant l'appel : un expert en sinistres, en priorité",
    },
    "injury": {
        "en": "A possible injury is never fast-tracked",
        "fr": "Une blessure possible n'est jamais traitée en mode rapide",
    },
    "closer_look": {
        "en": "Two or more signs and a high closer-look score: special investigations is asked to review",
        "fr": "Deux signes ou plus et une note élevée : le service des enquêtes est invité à examiner",
    },
    "open": {
        "en": "A home open to the weather goes to an adjuster",
        "fr": "Un logement ouvert aux intempéries est confié à un expert en sinistres",
    },
    "water": {
        "en": "Water still coming in goes to an adjuster",
        "fr": "De l'eau qui entre encore : confié à un expert en sinistres",
    },
    "fast_track_paused": {
        "en": "Fast-track is paused for this check while its inputs are reviewed",
        "fr": "Le traitement rapide est suspendu pendant la révision de cette vérification",
    },
}


@dataclass(frozen=True, slots=True)
class RouteResult:
    route: str
    rules: tuple[str, ...]
    siu_referral: bool
    n_signs: int


def decide(
    features: Mapping[str, float],
    p_size: float,
    p_fraud: float,
    *,
    size_threshold: float,
    fraud_threshold: float,
    urgent_safety: bool = False,
    fast_track_paused: bool = False,
) -> RouteResult:
    rules: list[str] = []
    n_signs = len(signs_present(features))
    siu = p_fraud >= fraud_threshold and n_signs >= 2
    if urgent_safety:
        rules.append("urgent")
        if siu:
            rules.append("closer_look")
        return RouteResult("adjuster", tuple(rules), siu, n_signs)
    if siu:
        rules.append("closer_look")
        if features.get("injury_reported"):
            rules.append("injury")
        return RouteResult("special_investigation", tuple(rules), True, n_signs)
    adjuster = p_size >= size_threshold
    if features.get("injury_reported"):
        rules.append("injury")
        adjuster = True
    if features.get("roof_or_window_opening"):
        rules.append("open")
        adjuster = True
    if features.get("water_still_entering"):
        rules.append("water")
        adjuster = True
    if not adjuster and fast_track_paused:
        rules.append("fast_track_paused")
        adjuster = True
    return RouteResult("adjuster" if adjuster else "fast_track", tuple(rules), False, n_signs)
