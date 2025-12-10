"""The route reveal at the end of a call (`call.ended.route`): who will look at the claim first, with three plain
reasons. The same routing checks the platform runs at hang-up, on what this call heard. Never a decision on the
claim."""

from __future__ import annotations

from typing import Any

from claimvoice.contracts import TriageInput
from claimvoice.dialogue.fakes import demo_policy_book
from claimvoice.ml.features import build_features
from claimvoice.ml.scorer import get_triage_scorer, route_label

FR_ROUTES = {
    "fast_track": "Traitement rapide",
    "adjuster": "Expert en sinistres",
    "special_investigation": "Examen approfondi",
}


def _policy_facts(engine: Any) -> dict[str, Any]:
    p = engine.policy
    rec = next((x for x in demo_policy_book() if x["policyNumber"] == p.policy_number), None) if p else None
    if rec is None:
        return {"line": p.line if p else "property", "region": p.region if p else engine.region, "status": "active"}
    line = rec["line"]
    key = "collision" if line == "auto" else "dwelling"
    cov: dict[str, Any] = next((c for c in rec["coverages"] if c["key"] == key), {})
    return {
        "line": line,
        "region": rec["region"],
        "status": rec["status"],
        "effective_from": rec["effectiveFrom"],
        "coverage_changed_at": rec.get("coverageChangedAt"),
        "deductible": cov.get("deductible"),
        "coverage_limit": cov.get("limit"),
        "prior_claims_36m": rec.get("priorClaims36m", 0),
    }


def preview_route(engine: Any) -> dict[str, Any] | None:
    facts = engine.call_facts()
    policy = _policy_facts(engine)
    features = build_features(engine.values(), policy, {"facts": facts})
    features_any: dict[str, Any] = {
        **features,
        "urgent_safety": facts.get("urgent_safety"),
        "region": policy.get("region"),
    }
    decision = get_triage_scorer().score(
        TriageInput(engine.call_id, engine.cfg.org_id, policy["line"], engine.loss_type or "", features_any)
    )
    lang = engine.language
    slots = engine.slots
    reasons = []
    for r in decision.reasons[:3]:
        at = (
            slots[r.slot_key].at_ms / 1000 if r.slot_key and r.slot_key in slots and slots[r.slot_key].turn_id else None
        )
        reasons.append({"text": r.text.get(lang, r.text["en"]), "atSeconds": at})
    label = FR_ROUTES[decision.route] if lang == "fr" else route_label(decision.route)
    return {"route": decision.route, "label": label, "reasons": reasons}
