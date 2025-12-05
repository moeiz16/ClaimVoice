"""The routing-check registry as the API reads it (`model_versions`, `check_signoffs`): mirroring the trained models'
registry file, building the Routing checks page (four questions), fact sheets, fairness, two-person sign-off and the
pack for the regulator. Everything a person reads is plain words and frequencies ("96 in 100")."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api.labels import lit
from claimvoice.claims.models import CheckSignoff, ModelVersion, RoutingDecisionRow
from claimvoice.platform.models import AuditEvent, User
from claimvoice.schemas import ml as w
from claimvoice.schemas.base import PersonRef

CHECK_ORDER = ("size", "closer_look")
SIDE_LABELS = {"claims": "Claims", "model_risk": "Model risk"}
STATUS_LABELS = {"healthy": "Working as expected", "watch": "Watch: storm week", "act": "Act"}
NEVER = [
    "denies a claim",
    "uses age, gender, language or postcode to route",
    "stops a person changing the route",
    "changes version without two sign-offs",
]
CAPTION = (
    "Two checks run when a call ends. A person can change any route. Reviewed monthly; a new version goes into use "
    "only after a claims supervisor and model risk both sign it off."
)
FAIRNESS_NOTE = "Age, language and region are never used to route a claim. We use them only here, to check fairness."


def load_registry() -> dict[str, Any] | None:
    try:
        from claimvoice.ml.registry import load_registry as ml_registry
    except ImportError:
        return None
    try:
        return dict(ml_registry())
    except (OSError, ValueError, KeyError):
        return None


async def mirror_registry(
    db: AsyncSession, org_id: str, registry: dict[str, Any], *, today: date
) -> list[ModelVersion]:
    """Upsert one `model_versions` row per check version from the registry file (stages as the file says)."""
    rows: list[ModelVersion] = []
    for key, check in (registry.get("checks") or {}).items():
        shared = {
            "name": check.get("name"),
            "question": check.get("question"),
            "decides": check.get("decides"),
            "sections": (check.get("factSheet") or {}).get("sections", []),
            "technical": check.get("technical") or {},
            "fairness": check.get("fairness") or {},
            "drift": check.get("drift") or {},
            "questions": check.get("questions") or {},
        }
        versions = sorted(check.get("versions") or [], key=lambda v: int(v["version"]))
        for v in versions:
            row = (
                await db.execute(
                    select(ModelVersion).where(
                        ModelVersion.org_id == org_id,
                        ModelVersion.check_key == key,
                        ModelVersion.version == int(v["version"]),
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                row = ModelVersion(org_id=org_id, check_key=key, version=int(v["version"]))
                db.add(row)
            row.stage = v.get("stage", "retired")
            row.algorithm = v.get("algorithm", "")
            row.trained_on = v.get("trainedOn", "")
            row.metrics = v.get("metrics") or {}
            row.gates = v.get("gates") or []
            row.fact_sheet = {**shared, "fairness": v.get("fairness") or shared["fairness"]}
            row.mlflow_run_id = v.get("runId")
            rows.append(row)
    await db.flush()
    return rows


# ---------------------------------------------------------------- reading


async def versions(db: AsyncSession, org_id: str, key: str) -> list[ModelVersion]:
    return list(
        (
            await db.execute(
                select(ModelVersion)
                .where(ModelVersion.org_id == org_id, ModelVersion.check_key == key)
                .order_by(ModelVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )


async def signoffs(db: AsyncSession, version_ids: list[str]) -> dict[str, list[CheckSignoff]]:
    if not version_ids:
        return {}
    rows = (
        (await db.execute(select(CheckSignoff).where(CheckSignoff.model_version_id.in_(version_ids)))).scalars().all()
    )
    out: dict[str, list[CheckSignoff]] = {}
    for r in rows:
        out.setdefault(r.model_version_id, []).append(r)
    return out


def _metrics(m: dict[str, Any]) -> w.MetricSet:
    return w.MetricSet(
        auc=float(m.get("auc", 0)),
        pr_auc=float(m.get("prAuc", m.get("pr_auc", 0))),
        brier=float(m.get("brier", 0)),
        ece=float(m.get("ece", 0)),
        recall_at_threshold=m.get("recallAtThreshold"),
        precision_at_threshold=m.get("precisionAtThreshold"),
        threshold=m.get("threshold"),
    )


def _signoff_out(side: str, row: CheckSignoff | None, people: dict[str, User]) -> w.SignOff:
    user = people.get(row.user_id) if row else None
    return w.SignOff(
        side=lit(side),
        side_label=SIDE_LABELS[side],
        by=PersonRef(id=user.id, name=user.full_name) if user else None,
        at=row.signed_at if row else None,
        note=row.note if row else None,
        state="signed" if row else "waiting",
    )


def version_out(v: ModelVersion, signs: list[CheckSignoff], people: dict[str, User]) -> w.CheckVersion:
    by_side = {s.side: s for s in signs}
    gates = [
        w.GateResult(
            key=g["key"], label=g["label"], passed=bool(g["passed"]), value=float(g["value"]), limit=float(g["limit"])
        )
        for g in v.gates
    ]
    return w.CheckVersion(
        version=v.version,
        stage=lit(v.stage),
        algorithm=v.algorithm,
        in_use_since=v.in_use_since,
        trained_on=v.trained_on,
        metrics=_metrics(v.metrics),
        gates=gates,
        gates_passed=all(g.passed for g in gates),
        sign_offs=[_signoff_out(side, by_side.get(side), people) for side in ("claims", "model_risk")],
    )


def drift_status(v: ModelVersion) -> str:
    weeks = (v.fact_sheet.get("drift") or {}).get("weeks") or []
    if not weeks:
        return "healthy"
    last = weeks[-1].get("status", "stable")
    return {"act": "act", "watch": "watch"}.get(last, "healthy")


async def check_out(db: AsyncSession, org_id: str, key: str) -> w.Check | None:
    rows = await versions(db, org_id, key)
    in_use = next((r for r in rows if r.stage == "in_use"), None)
    if in_use is None:
        return None
    candidate = next((r for r in rows if r.stage == "candidate"), None)
    signs = await signoffs(db, [r.id for r in rows])
    people = await _people(db, [s.user_id for lst in signs.values() for s in lst])
    status = drift_status(in_use)
    last = max(signs.get(in_use.id, []), key=lambda s: s.signed_at, default=None)
    last_user = people.get(last.user_id) if last else None
    fs = in_use.fact_sheet
    return w.Check(
        key=lit(key),
        name=fs.get("name") or ("Size check" if key == "size" else "Closer-look check"),
        question=fs.get("question") or "",
        decides=fs.get("decides") or "",
        in_use=version_out(in_use, signs.get(in_use.id, []), people),
        candidate=version_out(candidate, signs.get(candidate.id, []), people) if candidate else None,
        status=lit(status),
        status_label=STATUS_LABELS[status],
        signed_by=PersonRef(id=last_user.id, name=last_user.full_name) if last_user else None,
    )


async def _people(db: AsyncSession, ids: list[str]) -> dict[str, User]:
    if not ids:
        return {}
    return {u.id: u for u in (await db.execute(select(User).where(User.id.in_(set(ids))))).scalars()}


def in_100(value: float | None) -> str:
    return f"{round((value or 0) * 100)} in 100"


def _fairness(v: ModelVersion) -> dict[str, Any]:
    return v.fact_sheet.get("fairness") or {}


async def questions(db: AsyncSession, org_id: str) -> list[w.Question]:
    size = await versions(db, org_id, "size")
    look = await versions(db, org_id, "closer_look")
    size_in = next((r for r in size if r.stage == "in_use"), None)
    look_in = next((r for r in look if r.stage == "in_use"), None)
    out: list[w.Question] = []
    if size_in is not None:
        given = (size_in.fact_sheet.get("questions") or {}).get("right") or {}
        recall = size_in.metrics.get("recallAtThreshold")
        baseline = ((size_in.fact_sheet.get("technical") or {}).get("baseline") or {}).get("recallAtThreshold")
        bars = given.get("bars") or [
            {"label": "Size check", "value": recall or 0, "ours": True},
            {"label": "Old rule of thumb", "value": baseline or 0, "ours": False},
        ]
        out.append(
            w.Question(
                key="right",
                question="How often is it right?",
                answer=given.get("answer")
                or f"Of the claims that turned out large or complex, the size check sent **{in_100(recall)}** to an "
                "adjuster first.",
                foot=given.get("foot") or "Tested on December 2025 claims it had never seen.",
                bars=[w.Bar(label=b["label"], value=float(b["value"]), ours=bool(b.get("ours"))) for b in bars],
            )
        )
    if look_in is not None:
        fair = _fairness(look_in)
        rows = fair.get("rows") or []
        given = (look_in.fact_sheet.get("questions") or {}).get("fair") or {}
        out.append(
            w.Question(
                key="fair",
                question="Is it fair?",
                answer=given.get("answer")
                or (
                    "**Every group** is within 1.5 points of the overall closer-look rate."
                    if fair.get("passed", True)
                    else "**Some groups** are outside the allowed band; the candidate cannot go into use."
                ),
                foot=given.get("foot") or FAIRNESS_NOTE,
                dots=[
                    w.Dot(
                        dimension=r["dimension"],
                        group=r["group"],
                        label=r["label"],
                        rate=float(r["flaggedRate"]),
                        count=int(r["count"]),
                        within_band=bool(r["withinBand"]),
                    )
                    for r in rows
                ],
                overall_rate=float(fair.get("overallRate", 0)),
                band=float(fair.get("band", 0.015)),
            )
        )
    if size_in is not None:
        weeks = (size_in.fact_sheet.get("drift") or {}).get("weeks") or []
        given = (size_in.fact_sheet.get("questions") or {}).get("like_learned") or {}
        status = drift_status(size_in)
        out.append(
            w.Question(
                key="like_learned",
                question="Are claims still like the ones it learned from?",
                answer=given.get("answer")
                or {
                    "healthy": "**Yes.** This week's claims look like the ones it learned from.",
                    "watch": "**Mostly.** Storm week brings more wind claims than usual, so we are watching closely.",
                    "act": "**No.** Fast-track is paused for this check until a person resumes it.",
                }[status],
                foot=given.get("foot") or "Weekly shift: Watch at 0.10, Act at 0.25.",
                weeks=[w.WeekColumn(label=x["label"], psi=float(x["psi"]), status=x["status"]) for x in weeks],
            )
        )
    candidate = next((r for r in size if r.stage == "candidate"), None) or next(
        (r for r in look if r.stage == "candidate"), None
    )
    if candidate is not None:
        current = size_in if candidate.check_key == "size" else look_in
        assert current is not None
        signs = (await signoffs(db, [candidate.id])).get(candidate.id, [])
        people = await _people(db, [s.user_id for s in signs])
        by_side = {s.side: s for s in signs}

        def gate(v: ModelVersion, k: str) -> dict[str, Any]:
            return next((g for g in v.gates if g["key"] == k), {})

        rows = [
            w.CompareRow(
                key="right",
                label="Large claims sent to an adjuster",
                in_use=in_100(current.metrics.get("recallAtThreshold")),
                candidate=in_100(candidate.metrics.get("recallAtThreshold")),
                better=(candidate.metrics.get("recallAtThreshold") or 0)
                >= (current.metrics.get("recallAtThreshold") or 0),
            ),
            w.CompareRow(
                key="investigators_agreed",
                label="Referrals investigators agreed with",
                in_use=in_100(look_in.metrics.get("precisionAtThreshold") if look_in else None),
                candidate=in_100(
                    candidate.metrics.get("precisionAtThreshold")
                    if candidate.check_key == "closer_look"
                    else (look_in.metrics.get("precisionAtThreshold") if look_in else None)
                ),
                better=None,
            ),
            w.CompareRow(
                key="fair",
                label="Fair across groups",
                in_use="Yes" if gate(current, "fair").get("passed", True) else "No",
                candidate="Yes" if gate(candidate, "fair").get("passed", True) else "No",
                better=None,
            ),
            w.CompareRow(
                key="reasons_same",
                label="Reasons stay the same",
                in_use=in_100(gate(current, "reasons_stable").get("value")),
                candidate=in_100(gate(candidate, "reasons_stable").get("value")),
                better=(gate(candidate, "reasons_stable").get("value") or 0)
                >= (gate(current, "reasons_stable").get("value") or 0),
            ),
        ]
        out.append(
            w.Question(
                key="replace",
                question="Should the new version replace it?",
                answer=f"Version {candidate.version} is **waiting for two sign-offs**: one for claims, one for "
                "model risk.",
                foot="A version goes into use only when every gate passes and two different people sign it off.",
                compare=rows,
                sign_offs=[_signoff_out(side, by_side.get(side), people) for side in ("claims", "model_risk")],
            )
        )
    return out


async def page(db: AsyncSession, org_id: str) -> w.RoutingChecks:
    checks = [c for c in [await check_out(db, org_id, k) for k in CHECK_ORDER] if c is not None]
    return w.RoutingChecks(caption=CAPTION, checks=checks, questions=await questions(db, org_id), never=list(NEVER))


def _technical(v: ModelVersion) -> w.Technical:
    t = v.fact_sheet.get("technical") or {}

    def ms(x: dict[str, Any] | None) -> w.MetricSet:
        return _metrics(x or {})

    return w.Technical(
        test=ms(t.get("test") or v.metrics),
        baseline=ms(t.get("baseline")),
        random_forest=ms(t["randomForest"]) if t.get("randomForest") else None,
        roc=[w.CurvePoint(x=float(p["x"]), y=float(p["y"])) for p in t.get("roc", [])],
        pr=[w.CurvePoint(x=float(p["x"]), y=float(p["y"])) for p in t.get("pr", [])],
        calibration=[
            w.CalibrationBin(predicted=float(b["predicted"]), observed=float(b["observed"]), count=int(b["count"]))
            for b in t.get("calibration", [])
        ],
        split=t.get("split", ""),
        features=list(t.get("features", [])),
    )


async def fact_sheet(db: AsyncSession, org_id: str, key: str) -> w.FactSheet | None:
    rows = await versions(db, org_id, key)
    current = next((r for r in rows if r.stage == "in_use"), None)
    if current is None:
        return None
    signs = await signoffs(db, [r.id for r in rows])
    people = await _people(db, [s.user_id for lst in signs.values() for s in lst])
    sections = [
        w.FactSection(key=s["key"], title=s["title"], body=list(s.get("body", [])))
        for s in current.fact_sheet.get("sections", [])
        if s.get("key")
        in {"for", "not_for", "looks_at", "never_looks_at", "tested", "limits", "fairness", "sign_offs", "technical"}
    ]
    if not any(s.key == "sign_offs" for s in sections):
        body = []
        for s in sorted(signs.get(current.id, []), key=lambda s: s.side):
            u = people.get(s.user_id)
            body.append(f"{SIDE_LABELS[s.side]}: {u.full_name if u else 'unknown'}: “{s.note}”")
        sections.append(
            w.FactSection(key="sign_offs", title="Who signed it off", body=body or ["Waiting for sign-off."])
        )
    return w.FactSheet(
        key=lit(key),
        name=current.fact_sheet.get("name") or key,
        version=current.version,
        sections=sections,
        technical=_technical(current),
        versions=[version_out(r, signs.get(r.id, []), people) for r in rows],
    )


async def fairness(db: AsyncSession, org_id: str, key: str, version: int | None) -> w.Fairness | None:
    rows = await versions(db, org_id, key)
    v = (
        next((r for r in rows if r.version == version), None)
        if version
        else next((r for r in rows if r.stage == "in_use"), None)
    )
    if v is None:
        return None
    f = _fairness(v)
    return w.Fairness(
        key=lit(key),
        version=v.version,
        overall_rate=float(f.get("overallRate", 0)),
        band=float(f.get("band", 0.015 if key == "closer_look" else 0.05)),
        passed=bool(f.get("passed", True)),
        rows=[
            w.FairnessRow(
                dimension=r["dimension"],
                group=r["group"],
                label=r["label"],
                count=int(r["count"]),
                flagged_rate=float(r["flaggedRate"]),
                true_positive_rate=r.get("truePositiveRate"),
                false_positive_rate=r.get("falsePositiveRate"),
                gap=float(r["gap"]),
                within_band=bool(r["withinBand"]),
            )
            for r in f.get("rows", [])
        ],
        note=FAIRNESS_NOTE,
    )


# ---------------------------------------------------------------- sign-off


class SignOffError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


async def sign(db: AsyncSession, org_id: str, key: str, version: int, *, side: str, user_id: str, note: str) -> bool:
    """Record one side's sign-off. Returns True when this sign-off put the version into use."""
    rows = await versions(db, org_id, key)
    v = next((r for r in rows if r.version == version), None)
    if v is None:
        raise LookupError(key)
    if v.stage != "candidate":
        raise SignOffError("already_decided", "Only a candidate version can be signed off.")
    if not all(g.get("passed") for g in v.gates):
        raise SignOffError("gates_failed", "A gate has not passed, so this version cannot be signed off.")
    existing = (await signoffs(db, [v.id])).get(v.id, [])
    if any(s.side == side for s in existing):
        raise SignOffError("already_signed", "This side has already signed this version.")
    if any(s.user_id == user_id for s in existing):
        raise SignOffError("already_signed", "The two sign-offs must come from two different people.")
    db.add(
        CheckSignoff(org_id=org_id, model_version_id=v.id, side=side, user_id=user_id, note=note, signed_at=clock.now())
    )
    promoted = len(existing) + 1 >= 2
    if promoted:
        for r in rows:
            if r.stage == "in_use":
                r.stage, r.retired_at = "retired", clock.now()
        v.stage, v.in_use_since = "in_use", clock.today()
    await db.flush()
    return promoted


# ---------------------------------------------------------------- the pack for the regulator


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(header)
    out.writerows(rows)
    return buf.getvalue()


def _markdown(sheet: w.FactSheet, check: w.Check | None) -> str:
    lines = [f"# {sheet.name}: fact sheet (version {sheet.version})", ""]
    if check:
        lines += [
            f"**Question:** {check.question}",
            "",
            f"**Decides:** {check.decides}",
            "",
            f"**Status:** {check.status_label}",
            "",
        ]
    for s in sheet.sections:
        lines += [f"## {s.title}", ""] + [f"- {b}" for b in s.body] + [""]
    t = sheet.technical
    lines += [
        "## For the technical reviewer",
        "",
        f"Split: {t.split}",
        "",
        "| Model | ROC AUC | PR AUC | Brier | Calibration error |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, m in (("In use (test)", t.test), ("Logistic baseline", t.baseline), ("Random forest", t.random_forest)):
        if m is not None:
            lines.append(f"| {name} | {m.auc:.3f} | {m.pr_auc:.3f} | {m.brier:.4f} | {m.ece:.3f} |")
    lines += ["", "Inputs: " + ", ".join(t.features), ""]
    lines += [
        "## Versions",
        "",
        "| Version | Stage | Gates passed | Claims sign-off | Model risk sign-off |",
        "|---:|---|---|---|---|",
    ]
    for v in sheet.versions:
        so = {s.side: s for s in v.sign_offs}
        lines.append(
            f"| {v.version} | {v.stage.replace('_', ' ')} | {'yes' if v.gates_passed else 'no'} | "
            f"{so['claims'].by.name if so['claims'].by else 'waiting'} | "
            f"{so['model_risk'].by.name if so['model_risk'].by else 'waiting'} |"
        )
    lines += ["", "No run timestamps are recorded in this sheet. Nothing here decides or denies a claim."]
    return "\n".join(lines) + "\n"


async def regulator_pack(db: AsyncSession, org_id: str, org_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        readme = [
            f"# {org_name}: routing checks pack",
            "",
            "Prepared for a regulator's review of how ClaimVoice routes claims after a call. Designed to support the",
            "NAIC Model Bulletin on the Use of AI Systems by Insurers (governance, testing for unfair discrimination,",
            "explainability). Contents:",
            "",
            "- fact-sheets/: one plain-language fact sheet per routing check, with the technical fold",
            "- fairness.csv: rates by region, language and age band (used only for testing, never to route)",
            "- drift.csv: weekly input shift (Watch 0.10, Act 0.25)",
            "- sign-offs.csv: every version's two sign-offs",
            "- routing-summary.csv: routes chosen by the checks and by people, with overrides",
            "- audit-extract.csv: routing-related entries from the hash-chained activity log",
            "",
            "A routing check never denies a claim. It decides who looks first, and a person can change any route.",
        ]
        z.writestr("README.md", "\n".join(readme) + "\n")
        fairness_rows: list[list[Any]] = []
        drift_rows: list[list[Any]] = []
        sign_rows: list[list[Any]] = []
        for key in CHECK_ORDER:
            sheet = await fact_sheet(db, org_id, key)
            if sheet is None:
                continue
            z.writestr(f"fact-sheets/{key}.md", _markdown(sheet, await check_out(db, org_id, key)))
            for v in sheet.versions:
                f = await fairness(db, org_id, key, v.version)
                for r in f.rows if f else []:
                    fairness_rows.append(
                        [
                            key,
                            v.version,
                            r.dimension,
                            r.label,
                            r.count,
                            round(r.flagged_rate, 4),
                            round(r.gap, 4),
                            "yes" if r.within_band else "no",
                        ]
                    )
                for s in v.sign_offs:
                    sign_rows.append(
                        [
                            key,
                            v.version,
                            v.stage,
                            s.side_label,
                            s.by.name if s.by else "",
                            s.at.isoformat() if s.at else "",
                            s.note or "",
                            s.state,
                        ]
                    )
            current = next((r for r in await versions(db, org_id, key) if r.stage == "in_use"), None)
            for wk in ((current.fact_sheet.get("drift") or {}).get("weeks") or []) if current else []:
                drift_rows.append([key, current.version if current else "", wk["label"], wk["psi"], wk["status"]])
        z.writestr(
            "fairness.csv",
            _csv(
                ["check", "version", "dimension", "group", "claims", "flagged_rate", "gap", "within_band"],
                fairness_rows,
            ),
        )
        z.writestr("drift.csv", _csv(["check", "version", "week", "psi", "status"], drift_rows))
        z.writestr(
            "sign-offs.csv",
            _csv(["check", "version", "stage", "side", "person", "signed_at", "note", "state"], sign_rows),
        )
        decisions = (
            (await db.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.org_id == org_id))).scalars().all()
        )
        summary: dict[tuple[str, str, bool], int] = {}
        for d in decisions:
            k = (d.model_route, d.route, d.override_route is not None)
            summary[k] = summary.get(k, 0) + 1
        z.writestr(
            "routing-summary.csv",
            _csv(
                ["route_from_checks", "route_now", "changed_by_a_person", "claims"],
                [[a, b, "yes" if c else "no", n] for (a, b, c), n in sorted(summary.items())],
            ),
        )
        events = (
            (
                await db.execute(
                    select(AuditEvent)
                    .where(AuditEvent.org_id == org_id)
                    .where(
                        AuditEvent.action.startswith("claim.route")
                        | AuditEvent.action.startswith("check.")
                        | AuditEvent.action.startswith("siu.")
                    )
                    .order_by(AuditEvent.seq)
                )
            )
            .scalars()
            .all()
        )
        z.writestr(
            "audit-extract.csv",
            _csv(
                ["seq", "at", "person", "action", "summary", "hash"],
                [[e.seq, e.at.isoformat(), e.actor_label, e.action, e.summary, e.hash] for e in events],
            ),
        )
        z.writestr("manifest.json", json.dumps({"org": org_name, "files": sorted(z.namelist())}, indent=2))
    return buf.getvalue()
