# Compliance controls: where each one lives and what tests it

ClaimVoice is **designed to support** the obligations below. It is not certified against any of them, is not
endorsed by any regulator and is not legal advice. This page maps each obligation to the control in the product, the
code that implements it and the tests or evaluation gates that check it, so a reviewer can follow the claim to the
code in one step. Background: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md),
[ADR 0004](adr/0004-routing-checks.md) and [ADR 0005](adr/0005-consent-card-numbers-and-people-in-the-loop.md).

Paths are relative to `backend/` unless they start with `eval/` or `frontend/`. Gate values are from
[eval/RESULTS.md](../eval/RESULTS.md).

## Call-recording consent (all-party and one-party regions)

| Control | Code | Checked by |
|---|---|---|
| Consent is the first question on every call; nothing is asked before it except the greeting | `claimvoice/dialogue/stages.py` (stage order), `claimvoice/dialogue/machine.py` | `tests/dialogue/test_engine.py::test_consent_is_asked_first_and_nothing_is_kept_before_the_yes`; eval gate *Consent asked first* = 1.000 over 38 scripted callers |
| In all-party regions (Canadian provinces served, California, Washington, Florida, Illinois) nothing is kept before the yes; turns are held, then released in order | `claimvoice/reference.py` (default rules), `claimvoice/dialogue/machine.py` | `test_held_turns_are_released_in_order_once_consent_is_given`; eval gate *All-party calls: nothing kept before the yes* = 1.000 (29 calls) |
| A no stops the recording, marks transcript turns not retained and purges them at hang-up; the claim file (notes) is kept and a person is offered | `claimvoice/dialogue/machine.py`, `claimvoice/calls/sink.py`, `claimvoice/calls/closing.py` | `test_consent_refused_stops_recording_and_offers_a_person`; `tests/platform_api/test_sink.py::test_refused_consent_keeps_notes_but_not_the_transcript` |
| Rules are data per region, editable in Settings, but an all-party region cannot be weakened to one-party | `claimvoice/settings/service.py`, `claimvoice/api/routes/settings.py` | `tests/platform_api/test_admin.py::test_all_party_consent_cannot_be_weakened` |
| Urgent safety outranks consent (a caller who smells gas is told to get out before anything else) | `claimvoice/dialogue/machine.py` (global events) | `test_urgent_safety_outranks_consent` |
| The quality scorer checks consent order and the regional rule on every call | `claimvoice/qa/rubric.py` (`consent_first`, `consent_rule`) | `eval/qa/labels.yml`; eval agreement 1.00 on both items |

## PCI DSS: no card numbers by voice

| Control | Code | Checked by |
|---|---|---|
| The line never asks for payment details | `claimvoice/dialogue/scripts/*.yml` (no payment prompt exists) | Script review; quality rubric `no_card_numbers` |
| Every caller utterance passes card-number removal (13 to 19 digits that pass the Luhn check, written or spoken, in English or French) **before** understanding, storage, SSE or logs | `claimvoice/nlu/redaction.py` | `tests/dialogue/test_parse.py::test_card_numbers_are_removed_written_or_spoken`, `tests/test_adapters.py::test_card_numbers_are_removed_but_policy_and_phone_numbers_are_kept`, `tests/dialogue/test_engine.py::test_card_numbers_are_removed_before_anything_is_stored` |
| Policy numbers, phone numbers and dates survive redaction | `claimvoice/nlu/redaction.py` | `test_policy_phone_and_dates_survive_redaction` |
| The recording is silenced for that moment (a hatched "hush" on the waveform) and the caller is told not to share card numbers on this line | `claimvoice/voice/recorder.py` (`hush`), `claimvoice/dialogue/machine.py` | Eval gates *Card numbers caught and removed* = 1.000 and *Card numbers stored anywhere* = **0** (every stored text is checked) |
| Interim (partial) captions are never stored or replayed | `claimvoice/calls/sink.py` | `tests/platform_api/test_sink.py::test_partial_captions_are_never_stored_or_replayed` |

## NAIC Model Bulletin on the Use of AI Systems by Insurers

| Expectation | Control | Code | Checked by |
|---|---|---|---|
| Governance and accountability | Two different people sign a version (a claims supervisor and compliance for model risk) before it goes into use; a failed gate blocks sign-off | `claimvoice/api/routes/checks.py`, `claimvoice/ml/registry.py` | `tests/platform_api/test_admin.py::test_two_different_people_sign_off_a_candidate`, `test_a_failed_gate_blocks_sign_off` |
| Testing for unfair discrimination | Region, language and age band are never inputs; they are used only to measure rate gaps (closer look ±1.5 points, fast-track ±5 points) | `claimvoice/ml/features.py`, `claimvoice/ml/evaluate.py` | `tests/ml/test_ml.py::test_no_protected_attribute_or_proxy_is_a_model_input`, `test_age_bands_are_for_fairness_only`, `test_scoring_ignores_fairness_groups`; eval gates: largest gap 0.035 (size), 0.003 (closer look) |
| No voice-derived signals | No stress, accent, pitch or speech-rate features | `claimvoice/ml/features.py` | `test_no_protected_attribute_or_proxy_is_a_model_input` |
| Explainability | Top three reasons per route from SHAP, written as plain sentences in English and French and linked to the moment in the call; SHAP stability is a gate | `claimvoice/ml/reasons.py`, `claimvoice/calls/closing.py` | `test_reasons_are_plain_sentences`; eval gates: SHAP top-5 Jaccard 1.00 (size), 0.80 (closer look) |
| Model documentation | A fact sheet per check, generated without run timestamps | `claimvoice/ml/cards.py` → [docs/model-cards/](model-cards/) | `tests/platform_api/test_admin.py::test_fact_sheet_and_fairness` |
| Monitoring | Weekly PSI on scores (Watch 0.10, Act 0.25), and a simulated shift that must raise the alarm | `claimvoice/ml/metrics.py`, `eval/suites/models.py` | Eval gates: worst week 0.050 / 0.031; simulated shift 0.45 |
| Human oversight, no adverse decision by a model | Fixed rules win over scores (urgent safety and injuries never fast-track); a closer-look referral needs at least two signs and is a request for review; anyone allowed can change a route with a reason (audited); no endpoint approves or denies a claim | `claimvoice/ml/routing.py`, `claimvoice/api/routes/claims.py` | `test_rules_always_win`, `test_injury_and_urgent_safety_are_never_fast_tracked`, `tests/platform_api/test_claims.py::test_accept_then_change_a_route`, `tests/platform_api/test_rbac.py::test_nobody_can_approve_or_deny_a_claim` |

## Canada: PIPEDA and Québec Law 25

| Obligation | Control | Code | Checked by |
|---|---|---|---|
| Person responsible for personal information | A privacy officer on file per organisation (Priya Sandhu in the seed), required in Settings | `claimvoice/settings/service.py` | `tests/platform_api/test_admin.py::test_handoff_rules_languages_retention_privacy_validation` |
| Retention limits | Retention per organisation for recordings, transcripts and photos; the retention job removes what is due, keeps the claim record and writes an audit entry | `claimvoice/settings/retention.py` | `test_retention_removes_old_recordings_and_transcripts_but_keeps_claims` |
| Deletion requests | Retention settings show how many deletion requests are waiting; the request workflow itself is not built (see Limits below) | `claimvoice/settings/service.py` | – |
| Telling people about decisions made by automated processing alone | ClaimVoice makes no such decision: routing only decides who looks first, and a person can change it | `claimvoice/ml/routing.py` | `test_nobody_can_approve_or_deny_a_claim` |
| French first for Québec callers (Charter of the French language) | Bilingual scripts; the line answers in French, follows a switch mid-call and keeps an English line beside each French turn for staff | `claimvoice/dialogue/scripts/`, `claimvoice/dialogue/machine.py` | `test_caller_can_switch_to_french`, `test_french_lines_carry_an_english_version_for_staff`; eval gate *French calls completed* = 1.000 (9 calls); rubric item `language_honoured` |
| Photos without location | Uploaded photos are re-encoded from pixels only (no EXIF or GPS); HEIC is converted to JPEG on the phone | `claimvoice/api/routes/claims.py`, `frontend/app/pages/p/` | `tests/platform_api/test_claims.py::test_photo_link_upload_strips_location` |

## GLBA privacy and safeguards (and general security)

| Control | Code | Checked by |
|---|---|---|
| Phone, email and postal code masked in every response; the date of birth is used only to verify identity and is never returned | `claimvoice/schemas/policies.py`, `claimvoice/calls/views.py`, `claimvoice/policies/directory.py` | `tests/test_adapters.py::test_fake_sms_masks_the_number`, API shape tests |
| Tenant isolation: every query filters by organisation; another organisation's ids are 404 | `claimvoice/api/context.py`, every route | `tests/platform_api/test_tenancy.py` (four tests) |
| Role-based access (six roles), with closer-look details stripped for people without `siu:read` | `claimvoice/platform/permissions.py` | `tests/platform_api/test_rbac.py::test_permission_matrix_is_enforced`, `test_siu_fields_are_stripped_without_siu_read` |
| Argon2id passwords, short sessions (30 min idle, 12 h absolute), CSRF on unsafe methods, rate limits on sign-in | `claimvoice/platform/security.py`, `sessions.py`, `ratelimit.py` | `tests/platform_api/test_auth.py`, `test_conventions.py::test_rate_limit_on_auth_routes` |
| Security headers and a request id on every response | `claimvoice/api/middleware.py` | `tests/test_api.py::test_every_response_has_request_id_and_security_headers` |
| Tamper-evident activity log: hash-chained per organisation, verified on demand | `claimvoice/platform/audit.py`, `auditlog.py` | `tests/test_platform.py::test_audit_chain_verifies_and_detects_tampering`, `test_audit_chain_detects_deletion`, `tests/platform_api/test_admin.py::test_activity_log_is_hash_chained_and_tamper_evident` |
| Public demo calls from the landing page are purged after they end | `claimvoice/calls/closing.py` (`schedule_public_demo_purge`, `purge_public_demo`) | `tests/platform_api/test_calls.py::test_public_demo_line` covers the demo line; the purge has no dedicated test |

## A person always within reach

| Control | Code | Checked by |
|---|---|---|
| Hand-off reachable from every stage (caller asks, urgent safety, distress, low confidence, failed lookup) | `claimvoice/dialogue/stages.py` | `tests/test_dialogue.py::test_hand_off_is_reachable_from_every_stage`; eval gate *Safety and hand-off triggers caught* = 1.000 (10 scenarios) |
| Asking for a person works at once in either language | `claimvoice/dialogue/machine.py`, `claimvoice/nlu/fake.py` | `test_asking_for_a_person_hands_off_at_once_in_either_language` |
| Two turns not understood lead to a person, never a loop | `claimvoice/dialogue/machine.py` | `test_two_turns_not_understood_hand_off` |
| Urgent safety always reaches a person and is never turned into a call-back | `claimvoice/dialogue/machine.py` | `test_urgent_safety_never_falls_back_to_a_call_back` |
| Supervisor listen, whisper, take over and hand back, each audited | `claimvoice/voice/lines.py`, `claimvoice/api/routes/calls.py` | `tests/platform_api/test_calls.py::test_whisper_is_staff_only_audited_and_reaches_the_line`, `test_take_over_say_and_hand_back`, `tests/voice/test_runtime.py::test_take_over_say_and_hand_back_through_line_control` |
| The quality scorer marks a late or missed hand-off and says how late | `claimvoice/qa/scorer.py` | `tests/qa/test_scorer.py::test_late_hand_off_says_how_late`, `test_urgent_call_is_queued_because_a_hand_off_rule_applied` |

## Accessibility

| Control | Where | Checked by |
|---|---|---|
| Captions for every spoken line; "Read instead" transcript; a typed call when the microphone or speech recognition is unavailable | `frontend/app/pages/call.vue`, `frontend/app/pages/index.vue` | Web unit tests (`frontend/tests/landing.test.ts`, `transcript.test.ts`) and browser runs |
| Status never shown by colour alone (every route, band and flag carries an icon and a word); keyboard access; visible focus; reduced motion honoured | `frontend/app/components/` | `frontend/DESIGN.md` §13; browser runs with reduced motion |

## Limits

- Consent, card-number removal and hand-off are tested on scripted callers and recorded test calls, not on a
  real phone network; the demo line is a browser call.
- The closer-look check is trained and tested on synthetic data with documented injected patterns, so its fairness
  and accuracy numbers describe the method, not a real book of business.
- Deletion requests are counted, not worked: a request inbox for the privacy officer is future work.
- Nothing here has been reviewed by a regulator or counsel. Treat the mapping as engineering evidence, not a legal
  opinion.
