"""Settings, routing checks (sign-off, fairness, the regulator pack), call quality, the activity log and retention."""

import io
import zipfile
from datetime import timedelta

from sqlalchemy import select, update

from claimvoice import clock
from claimvoice.calls.models import Call, CallTurn
from claimvoice.claims.models import Claim
from claimvoice.platform import db
from claimvoice.platform.models import AuditEvent

# ---------------------------------------------------------------- settings


async def test_settings_overview_and_sections(sup):
    body = await sup.j("/api/v1/settings")
    assert body["privacy"]["privacyOfficerName"] == "Priya Sandhu"
    assert body["retention"]["cardNumberMoments"] == "always_removed"
    assert body["retention"]["refusedConsentTranscripts"] == "not_kept"
    assert body["handoffRules"]["urgentSafetyAlways"] is True
    assert body["consentRules"] >= 8 and body["scripts"] == 6
    scripts = await sup.j("/api/v1/settings/scripts")
    assert [s["lossType"] for s in scripts] == ["collision", "hail", "wind", "water", "fire", "theft"]
    wind = await sup.j("/api/v1/settings/scripts/wind")
    assert wind["questions"] and all(q["prompt"]["en"] and q["prompt"]["fr"] for q in wind["questions"])
    preview = await sup.get("/api/v1/settings/scripts/wind/preview?language=fr&index=0")
    assert preview.status_code == 200 and preview.headers["content-type"] == "audio/wav"


async def test_saving_a_script_makes_a_new_version(api_factory):
    admin = await api_factory("admin")
    current = await admin.j("/api/v1/settings/scripts/theft")
    questions = current["questions"]
    questions[0]["prompt"]["en"] = "What exactly was taken?"
    res = await admin.put("/api/v1/settings/scripts/theft", {"questions": questions, "note": "Shorter first question"})
    assert res.status_code == 200, res.text
    assert res.json()["version"] == current["version"] + 1
    assert res.json()["updatedBy"]["name"] == "Nadia Kassem"
    bad = await admin.put("/api/v1/settings/scripts/theft",
                          {"questions": [{**questions[0], "slotKey": "favourite_colour"}], "note": "x"})
    assert bad.status_code == 422
    no_note = await admin.put("/api/v1/settings/scripts/theft", {"questions": questions, "note": " "})
    assert no_note.status_code == 422
    audit = (await admin.j("/api/v1/audit?action=settings.script_changed"))["items"]
    assert audit and "theft" in audit[0]["summary"].lower()


async def test_all_party_consent_cannot_be_weakened(api_factory):
    admin = await api_factory("admin")
    weaken = await admin.put("/api/v1/settings/consent-rules/US-CA",
                             {"rule": "one_party", "announcement": {"en": "We record.", "fr": "Nous enregistrons."}})
    assert weaken.status_code == 422
    rules = {r["region"]: r for r in await admin.j("/api/v1/settings/consent-rules")}
    assert rules["US-CA"]["rule"] == "all_party" and "§632" in rules["US-CA"]["basis"]
    co = await admin.put("/api/v1/settings/consent-rules/US-CO",
                         {"rule": "all_party", "announcement": {"en": "This call is recorded. Okay?",
                                                                "fr": "Cet appel est enregistré. D'accord?"}})
    assert co.status_code == 200 and co.json()["rule"] == "all_party" and co.json()["isDefault"] is False


async def test_handoff_rules_languages_retention_privacy_validation(api_factory):
    admin = await api_factory("admin")
    rules = await admin.j("/api/v1/settings/handoff-rules")
    assert (await admin.put("/api/v1/settings/handoff-rules", {**rules, "lowConfidenceTurns": 9})).status_code == 422
    ok = await admin.put("/api/v1/settings/handoff-rules", {**rules, "maxWaitSeconds": 120, "urgentSafetyAlways": False})
    assert ok.status_code == 200 and ok.json()["maxWaitSeconds"] == 120 and ok.json()["urgentSafetyAlways"] is True
    langs = await admin.j("/api/v1/settings/languages")
    no_fr = await admin.put("/api/v1/settings/languages", {**langs, "enabled": ["en"], "default": "en"})
    assert no_fr.status_code == 422  # Québec is served
    retention = await admin.j("/api/v1/settings/retention")
    assert (await admin.put("/api/v1/settings/retention", {**retention, "recordingsYears": 30})).status_code == 422
    privacy = await admin.put("/api/v1/settings/privacy", {"privacyOfficerName": "Priya Sandhu",
                                                           "privacyOfficerEmail": "not-an-email", "privacyNoticeUrl": None})
    assert privacy.status_code == 422


# ---------------------------------------------------------------- routing checks


async def test_routing_checks_page_answers_four_questions(sup):
    body = await sup.j("/api/v1/routing-checks")
    assert [c["key"] for c in body["checks"]] == ["size", "closer_look"]
    size = body["checks"][0]
    assert size["inUse"]["version"] == 5 and size["inUse"]["stage"] == "in_use"
    assert size["candidate"]["version"] == 6
    assert {s["side"] for s in size["inUse"]["signOffs"]} == {"claims", "model_risk"}
    assert all(s["state"] == "signed" for s in size["inUse"]["signOffs"])
    assert all(s["state"] == "waiting" for s in size["candidate"]["signOffs"])
    assert [q["key"] for q in body["questions"]] == ["right", "fair", "like_learned", "replace"]
    assert "denies a claim" in body["never"]
    fair = next(q for q in body["questions"] if q["key"] == "fair")
    assert fair["dots"] and fair["band"]


async def test_fact_sheet_and_fairness(sup):
    sheet = await sup.j("/api/v1/routing-checks/closer_look")
    assert sheet["version"] == 5 and sheet["sections"]
    assert sheet["technical"]["test"]["prAuc"] > sheet["technical"]["baseline"]["prAuc"]
    fairness = await sup.j("/api/v1/routing-checks/closer_look/fairness")
    assert fairness["passed"] and fairness["rows"] and "never used to route" in fairness["note"]
    v4 = await sup.j("/api/v1/routing-checks/size/fairness?version=4")
    assert v4["version"] == 4
    assert (await sup.get("/api/v1/routing-checks/nonsense")).status_code == 404


async def test_two_different_people_sign_off_a_candidate(api_factory):
    renee = await api_factory("supervisor")
    priya = await api_factory("compliance")
    mismatch = await renee.post("/api/v1/routing-checks/size/versions/6/sign-off", {"version": 5, "note": "ok"})
    assert mismatch.status_code == 422
    first = await renee.post("/api/v1/routing-checks/size/versions/6/sign-off",
                             {"version": 6, "note": "Fast-track mix still right for storm week."})
    assert first.status_code == 200, first.text
    assert first.json()["candidate"]["version"] == 6
    twice = await renee.post("/api/v1/routing-checks/size/versions/6/sign-off", {"version": 6, "note": "again"})
    assert twice.status_code == 409 and twice.json()["code"] == "already_signed"
    second = await priya.post("/api/v1/routing-checks/size/versions/6/sign-off",
                              {"version": 6, "note": "Gates pass; fairness within band."})
    assert second.status_code == 200
    assert second.json()["inUse"]["version"] == 6 and second.json()["candidate"] is None
    retired = await priya.post("/api/v1/routing-checks/size/versions/5/sign-off", {"version": 5, "note": "late"})
    assert retired.status_code == 409
    admin = await api_factory("admin")
    actions = {e["action"] for e in (await admin.j("/api/v1/audit?action=check.&pageSize=100"))["items"]}
    assert {"check.signed_off", "check.version_in_use"} <= actions


async def test_a_failed_gate_blocks_sign_off(api_factory):
    from claimvoice.claims.models import ModelVersion

    async with db.sessionmaker()() as s:
        row = (await s.execute(select(ModelVersion).where(ModelVersion.check_key == "closer_look",
                                                          ModelVersion.version == 6))).scalar_one()
        row.gates = [{**g, "passed": g["key"] != "fair"} for g in row.gates]
        await s.commit()
    await db.dispose()
    priya = await api_factory("compliance")
    res = await priya.post("/api/v1/routing-checks/closer_look/versions/6/sign-off", {"version": 6, "note": "ok"})
    assert res.status_code == 409 and res.json()["code"] == "gates_failed"


async def test_regulator_pack(api_factory):
    priya = await api_factory("compliance")
    res = await priya.get("/api/v1/routing-checks/regulator-pack")
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    names = set(zipfile.ZipFile(io.BytesIO(res.content)).namelist())
    assert {"README.md", "fact-sheets/size.md", "fact-sheets/closer_look.md", "fairness.csv", "drift.csv",
            "sign-offs.csv", "routing-summary.csv", "audit-extract.csv", "manifest.json"} <= names
    z = zipfile.ZipFile(io.BytesIO(res.content))
    assert "Renée Kowalchuk" in z.read("sign-offs.csv").decode()
    assert "never denies a claim" in z.read("README.md").decode()
    wall_clock_month = "-".join(("2026", "11"))
    assert wall_clock_month not in z.read("fact-sheets/size.md").decode()
    entries = (await priya.j("/api/v1/audit?action=check.regulator_pack"))["items"]
    assert entries and entries[0]["actorLabel"] == "Priya Sandhu"


# ---------------------------------------------------------------- quality


async def test_rubric_and_queue(api_factory):
    owen = await api_factory("compliance")
    rubric = await owen.j("/api/v1/qa/rubric")
    assert len(rubric) == 11 and sum(1 for r in rubric if r["bead"]) == 6
    queue = await owen.j("/api/v1/qa/queue?pageSize=100")
    assert queue["items"] and all(q["status"] == "needs_review" for q in queue["items"])
    assert all(len(q["beads"]) == 6 and q["reasonQueued"] for q in queue["items"])
    flagged = [q["band"] == "failed" for q in queue["items"]]
    assert flagged == sorted(flagged, reverse=True)
    one = queue["items"][0]
    failing = next((b["key"] for b in one["beads"] if b["passed"] is False), None)
    if failing:
        filtered = await owen.j(f"/api/v1/qa/queue?item={failing}&pageSize=100")
        assert any(q["callId"] == one["callId"] for q in filtered["items"])
    everything = await owen.j("/api/v1/qa/queue?status=all&pageSize=100")
    assert everything["total"] > queue["total"]


async def test_reviewing_a_call_and_agreement(api_factory):
    owen = await api_factory("compliance")
    queue = (await owen.j("/api/v1/qa/queue?pageSize=100"))["items"]
    call_id = queue[-1]["callId"]
    score = await owen.j(f"/api/v1/qa/calls/{call_id}")
    items = [i for i in score["items"] if i["passed"] is not None]
    no_note = await owen.post(f"/api/v1/qa/calls/{call_id}/review",
                              {"items": [{"key": items[0]["key"], "verdict": "disagree"}]})
    assert no_note.status_code == 422
    body = {"items": [{"key": i["key"], "verdict": "agree"} for i in items[1:]] +
            [{"key": items[0]["key"], "verdict": "disagree", "note": "The line did ask, just later."}],
            "note": "Listened end to end.", "coachingNote": "Ask consent before the first question."}  # fmt: skip
    res = await owen.post(f"/api/v1/qa/calls/{call_id}/review", body)
    assert res.status_code == 200 and res.json()["status"] == "reviewed"
    assert next(i for i in res.json()["items"] if i["key"] == items[0]["key"])["reviewerVerdict"] == "disagree"
    agreement = await owen.j("/api/v1/qa/agreement")
    assert agreement["reviewedCalls"] >= 1 and 0 <= agreement["overall"] <= 1
    assert agreement["byItem"]


def test_cohen_kappa():
    from claimvoice.api.routes.qa import cohen_kappa

    assert cohen_kappa([]) is None
    assert cohen_kappa([(True, True), (False, False)]) == 1.0
    assert cohen_kappa([(True, False), (False, True)]) == -1.0


# ---------------------------------------------------------------- activity log and retention


async def test_activity_log_is_hash_chained_and_tamper_evident(api_factory):
    admin = await api_factory("admin")
    page = await admin.j("/api/v1/audit?pageSize=50")
    seqs = [e["seq"] for e in page["items"]]
    assert seqs == sorted(seqs, reverse=True)
    assert all(e["summary"] and e["actionLabel"] for e in page["items"])
    assert (await admin.j("/api/v1/audit/verify"))["ok"] is True
    csv = await admin.get("/api/v1/audit/export.csv?action=claim.")
    assert csv.status_code == 200 and csv.text.startswith("seq,at,person,action")
    org_id = (await admin.j("/api/v1/org"))["id"]
    async with db.sessionmaker()() as s:
        row = (await s.execute(select(AuditEvent).where(AuditEvent.org_id == org_id).order_by(AuditEvent.seq).limit(1)
                               .offset(3))).scalar_one()
        original = row.summary
        row.summary = "Nothing happened here."
        await s.commit()
    await db.dispose()
    broken = await admin.j("/api/v1/audit/verify")
    assert broken["ok"] is False and broken["firstBrokenSeq"] == 4
    async with db.sessionmaker()() as s:
        await s.execute(update(AuditEvent).where(AuditEvent.id == row.id).values(summary=original))
        await s.commit()
    await db.dispose()
    assert (await admin.j("/api/v1/audit/verify"))["ok"] is True


async def test_retention_removes_old_recordings_and_transcripts_but_keeps_claims(api_factory):
    from claimvoice.settings.retention import purge

    admin = await api_factory("admin")
    retention = await admin.j("/api/v1/settings/retention")
    await admin.put("/api/v1/settings/retention", {**retention, "recordingsYears": 1, "transcriptsYears": 1})
    claims_before = (await admin.j("/api/v1/claims"))["total"]
    result = await purge(now=clock.now() + timedelta(days=2 * 365))
    assert result.recordings > 0 and result.turns > 0
    async with db.sessionmaker()() as s:
        old = (await s.execute(select(Call).where(Call.state == "ended"))).scalars().first()
        turns = (await s.execute(select(CallTurn).where(CallTurn.call_id == old.id))).scalars().all()
        claims = (await s.execute(select(Claim))).scalars().all()
    await db.dispose()
    assert turns == [] and len(claims) >= claims_before
    sup = await api_factory("supervisor")
    claim = (await sup.j("/api/v1/claims?pageSize=100"))["items"][-1]
    rec = await sup.j(f"/api/v1/claims/{claim['id']}/recording")
    assert rec["available"] is False and "retention" in rec["reason"]
    entries = (await admin.j("/api/v1/audit?action=retention.purged"))["items"]
    assert entries and "claim files are kept" in entries[0]["summary"]
    after = await admin.j("/api/v1/settings/retention")
    assert after["lastPurgeAt"]
