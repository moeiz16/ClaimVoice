"""SHAP contributions turned into plain sentences (EN/FR), e.g. "Reported 11 days after the loss".

The scorer takes each feature's exact TreeSHAP contribution from XGBoost (`pred_contribs`), keeps the strongest few,
and words each one from the feature's value and the direction it pushed the score. No numbers that mean nothing to a
person (no probabilities, no "SHAP"), and never a protected attribute: they are not model inputs."""

from __future__ import annotations

from collections.abc import Mapping

from claimvoice.ml.features import FEATURE_LABELS

LOSS_WORDS = {
    "loss_collision": ("a collision", "une collision"),
    "loss_hail": ("hail", "la grêle"),
    "loss_wind": ("wind", "le vent"),
    "loss_water": ("water", "un dégât d'eau"),
    "loss_fire": ("fire or smoke", "un incendie"),
    "loss_theft": ("a theft or break-in", "un vol"),
}


def _days(hours: float) -> int:
    return max(1, round(hours / 24))


def phrase(feature: str, value: float, raises: bool) -> tuple[str, str]:
    """(English, French) sentence for one feature's push on a score."""
    v = value
    if feature in LOSS_WORDS:
        en, fr = LOSS_WORDS[feature]
        if v >= 1:
            return (
                (
                    f"Claims for {en} like this one are often larger",
                    f"Les réclamations pour {fr} comme celle-ci sont souvent plus importantes",
                )
                if raises
                else (
                    f"Claims for {en} like this are usually quick to price",
                    f"Les réclamations pour {fr} comme celle-ci sont habituellement simples à évaluer",
                )
            )
        return ("The kind of loss", "Le type de sinistre")
    if feature == "hours_loss_to_report":
        if v >= 48:
            return f"Reported {_days(v)} days after the loss", f"Déclaré {_days(v)} jours après le sinistre"
        return "Reported within hours of the loss", "Déclaré quelques heures après le sinistre"
    if feature == "days_policy_start_to_loss":
        if v <= 60:
            return (
                f"Policy started {int(v)} days before the loss",
                f"La police a commencé {int(v)} jours avant le sinistre",
            )
        years = int(v // 365)
        if years >= 1:
            return (
                f"Policy active {years} year{'s' if years > 1 else ''}",
                f"Police en vigueur depuis {years} an{'s' if years > 1 else ''}",
            )
        return f"Policy active {int(v // 30)} months", f"Police en vigueur depuis {int(v // 30)} mois"
    if feature == "days_coverage_change_to_loss":
        if v <= 90:
            return (
                f"Coverage was raised {int(v)} days before the loss",
                f"La couverture a été augmentée {int(v)} jours avant le sinistre",
            )
        return "No recent change to coverage", "Aucun changement récent de couverture"
    if feature == "prior_claims_36m":
        n = int(v)
        if n == 0:
            return "No other claims in the last 3 years", "Aucune autre réclamation en 3 ans"
        return (
            f"{n} other claim{'s' if n > 1 else ''} in the last 3 years",
            f"{n} autre{'s' if n > 1 else ''} réclamation{'s' if n > 1 else ''} en 3 ans",
        )
    if feature == "key_fact_corrections":
        n = int(v)
        if n == 0:
            return "The account stayed the same through the call", "Le récit est resté le même pendant l'appel"
        return (
            f"When, where or what happened changed {n} time{'s' if n > 1 else ''}",
            f"Le moment, le lieu ou le déroulement a changé {n} fois",
        )
    if feature == "damage_area_count":
        n = int(v)
        if n <= 1:
            return "Damage limited to one area", "Dommages limités à un seul endroit"
        return f"Damage to {n} different parts", f"Dommages à {n} endroits différents"
    if feature == "rooms_affected":
        n = int(v)
        if n <= 1:
            return "One room affected", "Une seule pièce touchée"
        return f"{n} rooms affected", f"{n} pièces touchées"
    if feature == "caller_damage_estimate_band":
        words = {
            0: ("No estimate given", "Aucune estimation donnée"),
            1: ("Caller expects under $2,000", "L'appelant prévoit moins de 2 000 $"),
            2: ("Caller expects $2,000 to $10,000", "L'appelant prévoit de 2 000 $ à 10 000 $"),
            3: ("Caller expects $10,000 to $50,000", "L'appelant prévoit de 10 000 $ à 50 000 $"),
            4: ("Caller expects over $50,000", "L'appelant prévoit plus de 50 000 $"),
        }
        return words.get(int(v), words[0])
    if feature == "vehicle_age_years":
        return f"Vehicle about {int(v)} years old", f"Véhicule d'environ {int(v)} ans"
    if feature == "deductible":
        return f"Deductible of ${int(v):,}", f"Franchise de {int(v):,} $".replace(",", " ")
    if feature == "description_words":
        return (
            ("A detailed account of what happened", "Un récit détaillé de ce qui s'est passé")
            if v >= 15
            else ("A short account of what happened", "Un récit bref de ce qui s'est passé")
        )
    if feature == "coverage_limit_log":
        return "The policy's coverage limit", "La limite de couverture de la police"
    yes = v >= 1
    pairs: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
        "injury_reported": (
            ("Someone may be hurt", "Une personne pourrait être blessée"),
            ("Nobody hurt", "Personne n'est blessé"),
        ),
        "other_party_involved": (
            ("Another party is involved", "Une autre partie est en cause"),
            ("No other party involved", "Aucune autre partie en cause"),
        ),
        "police_report_filed": (
            ("A police report was made", "Un rapport de police a été fait"),
            ("No police report", "Aucun rapport de police"),
        ),
        "vehicle_not_drivable": (
            ("The vehicle can't be driven", "Le véhicule ne peut pas rouler"),
            ("The vehicle can still be driven", "Le véhicule peut encore rouler"),
        ),
        "airbags_deployed": (
            ("The airbags went off", "Les coussins gonflables se sont déployés"),
            ("The airbags didn't go off", "Les coussins gonflables ne se sont pas déployés"),
        ),
        "water_still_entering": (
            ("Water is still coming in", "L'eau entre encore"),
            ("The water has stopped", "L'eau a cessé d'entrer"),
        ),
        "roof_or_window_opening": (
            ("The home is open to the weather", "Le logement est ouvert aux intempéries"),
            ("Nothing is open to the weather", "Rien n'est ouvert aux intempéries"),
        ),
        "roof_or_window_damage": (
            (
                "The roof, a window or a skylight is damaged",
                "Le toit, une fenêtre ou un puits de lumière est endommagé",
            ),
            ("No roof or window damage", "Aucun dommage au toit ni aux fenêtres"),
        ),
        "siding_or_fence_damage": (
            ("Siding or a fence is damaged", "Le revêtement ou une clôture est endommagé"),
            ("No siding or fence damage", "Aucun dommage au revêtement ni aux clôtures"),
        ),
        "home_not_livable": (
            ("The home can't be lived in", "Le logement n'est pas habitable"),
            ("The family can stay in the home", "La famille peut rester dans le logement"),
        ),
        "surge_event_match": (
            ("Matches the storm on record in the area", "Correspond à la tempête enregistrée dans le secteur"),
            ("Not part of an active storm", "Ne fait pas partie d'une tempête active"),
        ),
        "weather_confirms_loss": (
            ("Weather records confirm the storm", "Les relevés météo confirment la tempête"),
            ("No weather event to confirm it", "Aucun événement météo pour le confirmer"),
        ),
        "weather_contradicts_loss": (
            ("Weather records don't show a storm there", "Les relevés météo n'indiquent pas de tempête à cet endroit"),
            ("Weather records fit the account", "Les relevés météo concordent avec le récit"),
        ),
        "photos_promised": (
            ("Photos are on the way", "Des photos s'en viennent"),
            ("No photos promised", "Aucune photo promise"),
        ),
        "photos_declined": (
            ("Declined to send photos", "A refusé d'envoyer des photos"),
            ("Photos are on the way", "Des photos s'en viennent"),
        ),
        "theft_without_police_report": (
            ("Theft not reported to the police", "Vol non déclaré à la police"),
            ("Reported to the police", "Déclaré à la police"),
        ),
        "round_number_estimate": (
            (
                "A round-number estimate in the top band",
                "Une estimation en chiffre rond dans la tranche la plus élevée",
            ),
            ("No round-number estimate", "Pas d'estimation en chiffre rond"),
        ),
        "third_party_pressure": (
            (
                "Someone other than the policyholder pushed for a fast payment",
                "Une autre personne que l'assuré a insisté pour un paiement rapide",
            ),
            ("No pressure for a fast payment", "Aucune pression pour un paiement rapide"),
        ),
        "night_loss_no_witness": (
            ("Night-time loss with no witness or police report", "Sinistre de nuit sans témoin ni rapport de police"),
            ("Not a night-time loss without a witness", "Pas un sinistre de nuit sans témoin"),
        ),
        "policy_not_in_force": (
            ("Policy not in force on the loss date", "Police non en vigueur à la date du sinistre"),
            ("Policy in force on the loss date", "Police en vigueur à la date du sinistre"),
        ),
        "is_auto": (("An auto policy", "Une police auto"), ("A home policy", "Une police habitation")),
    }
    if feature in pairs:
        return pairs[feature][0] if yes else pairs[feature][1]
    label = FEATURE_LABELS.get(feature, feature.replace("_", " "))
    return label, label


# Inputs the models use that make poor reasons to a person (they describe the policy, not what happened).
NOT_SHOWN = frozenset({"deductible", "coverage_limit_log", "description_words", "is_auto", "vehicle_age_years"})


def _worth_saying(feature: str, values: Mapping[str, float]) -> bool:
    if feature in NOT_SHOWN:
        return False
    v = float(values.get(feature, 0.0))
    if feature == "rooms_affected" and v == 0:
        return False  # not a water or fire loss
    if feature == "caller_damage_estimate_band" and v == 0:
        return False
    if feature in ("vehicle_not_drivable", "airbags_deployed") and not values.get("is_auto"):
        return False
    return not (feature.startswith("loss_") and v == 0)  # "not hail" is not a reason


def top_reasons(
    contributions: Mapping[str, float], values: Mapping[str, float], *, k: int = 3, direction: str | None = None
) -> list[tuple[str, float, str, str]]:
    """[(feature, contribution, en, fr)] for the k strongest contributions, optionally only those that raise (or
    lower) the score."""
    items = [(f, c) for f, c in contributions.items() if abs(c) > 1e-6 and _worth_saying(f, values)]
    if direction == "raises":
        items = [x for x in items if x[1] > 0]
    elif direction == "lowers":
        items = [x for x in items if x[1] < 0]
    items.sort(key=lambda x: -abs(x[1]))
    out: list[tuple[str, float, str, str]] = []
    seen_text: set[str] = set()
    for f, c in items:
        en, fr = phrase(f, float(values.get(f, 0.0)), c > 0)
        if en in seen_text:
            continue
        seen_text.add(en)
        out.append((f, c, en, fr))
        if len(out) >= k:
            break
    return out
