# ClaimVoice API contract (v1)

The binding reference for ClaimVoice's module boundaries. The web app builds against Part 1 (HTTP), Part 4 (voice
signalling and the data-channel protocol) and the SSE events in §1.8. Part 2 is the data model, Part 3 the Python
interfaces between the voice runtime and the platform, Part 5 the dialogue state machine, Part 6 the routing models,
Part 7 the module map and Part 8 project conventions.

Changing a shape here means changing it in the same commit as the code. The code half lives in
`backend/claimvoice/schemas/*.py` (wire shapes, msgspec), `backend/claimvoice/contracts.py` (in-process interfaces),
`backend/claimvoice/dialogue/stages.py` (stages, events, transitions), `backend/claimvoice/platform/permissions.py`
(roles) and `backend/claimvoice/qa/rubric.py` (call-quality rubric).

---

# Part 1: HTTP API

## 1.0 Screens and the endpoints behind them

The web app's information architecture (`frontend/DESIGN.md` §3): one floating **dock** is the only navigation, with
**Lines · Claims · Quality · Routing checks · Settings**, and "the line you are on" (a mini player) once you listen.

| Route | Screen | Endpoints |
|---|---|---|
| `/` | Landing with the recorded call (static audio + captions) | `GET /meta`, `GET /auth/session` |
| `/call` | Ring the demo line (orb, captions, typed call, French) | `POST /demo/calls`, Part 4 signalling and data channel |
| `/sign-in` | Sign in, demo sign-in | `GET /auth/csrf`, `POST /auth/login`, `POST /auth/demo` |
| `/lines` | Line desk: surge ribbon, strips, hand-off tray, free people, finished this morning | `GET /switchboard`, SSE `/switchboard/stream`, `/surges/{id}/standby`, `/surges/{id}/questions`, `/calls/{id}/handoff/accept` |
| `/lines/[lineId]` (`lineId` = call id) | Live call: conversation, script track, live claim file, whisper input, take over | `GET /calls/{id}`, `/transcript`, `/claim-file`, SSE `/calls/{id}/stream`, `/listen`, `/whisper`, `/takeover`, `/say`, `/return`, `/handoff`, `/hangup` |
| dock player | The line you are on (Listening · Whisper · Take over) | `POST /calls/{id}/listen` (`ListenOut`), SSE `/calls/{id}/stream` |
| `/claims`, `/claims/[claimId]` | Claim ledger (filter pills by route); claim file: In short, What we heard, Where it goes | `GET /claims`, `/claims/{id}`, `/transcript`, `/recording`, `/recording/audio`, `/photos`, `/routing`, `/routing/accept`, `/routing/override`, `/siu`, `/siu/decision`, `PATCH /claims/{id}/file` |
| `/quality`, `/quality/[callId]` | Review queue with rubric beads; review opened at the flagged moment | `GET /qa/queue`, `/qa/calls/{callId}`, `POST …/review`, `GET /claims/{id}/recording` (by the call's claim) |
| `/routing`, `/routing/[check]` | Routing checks (four questions) and fact sheets | `GET /routing-checks`, `/routing-checks/{check}`, `/fairness`, `POST …/sign-off`, `GET /routing-checks/regulator-pack` |
| `/settings/{scripts,consent,handoff,languages,retention,people}` | Settings sections | §1.11, people §1.4 |
| `/activity` | Audit log, day-grouped sentences, "Record intact" | `GET /audit`, `/audit/verify`, `/audit/export.csv` |
| `/p/[token]` | Photo upload from the caller's phone | `GET /photo-links/{token}`, `POST /photo-links/{token}/photos` |

## 1.1 Conventions

- Base path **`/api/v1`**. The web app (Nuxt on :3040) forwards `/api/**` to the API on :8040 through a same-origin
  server route, so the browser sees one origin and cookies just work. The voice WebSocket fallback connects to :8040
  directly (cookies are shared across ports on the same host; the caller leg uses a bearer token anyway).
- JSON is **camelCase** on the wire (msgspec `rename="camel"`). Maps that keep their keys as written: `details`
  (audit), `data` (SSE and call events), `features` (models), `value` inside claim-file slots.
- **Plain-words fields.** Every code the UI might show travels with its label in the viewer's language
  (`route` + `routeLabel`, `stage.key` + `stage.label`, `lossType` + `lossTypeLabel`). The web app never maps codes
  to words itself, except for the static dictionary from `GET /meta`. Labels never contain technical terms (Part 8).
- **Language.** `Accept-Language: fr` (or the user's `preferredLanguage`) selects French labels. Transcript text and
  summaries stay in the call's language; `summaryEn` / `descriptionEn` carry an English version for adjusters.
- Ids are UUID strings. Human references: claims `CV-26-01842` (the number the caller hears), calls
  `CALL-260108-042`, policies `LM-AB-204118`. Live calls are also known by their line (`Line 1` … `Line n`).
  Timestamps are ISO-8601 UTC with offset (`2026-01-08T16:40:12+00:00`); the web app shows them in the org's zone
  (`America/Edmonton`) or the viewer's. The default demo moment is **Thursday 8 January 2026, 7:42 a.m. Calgary
  time** (`CLAIMVOICE_DEMO_TODAY=2026-01-08`, `CLAIMVOICE_DEMO_TIME=07:42`), the morning after an overnight Chinook
  windstorm. Calendar dates `YYYY-MM-DD`. Money: `{ amount, currency }` with CAD or USD.
  Regions are ISO 3166-2 (`CA-AB`, `CA-QC`, `US-CO`). Durations in seconds (`…Seconds`) unless named `…Ms`.
- **Demo clock.** "Today" and "now" come from the server clock (`clock.now()`), which `CLAIMVOICE_DEMO_TODAY`
  (default `2026-01-08`) shifts and `CLAIMVOICE_DEMO_TIME` can pin, shared by every process through
  `data/demo-clock.json`. **Every response carries `X-ClaimVoice-Now`** (ISO-8601 UTC). The web app keeps the
  offset to the browser clock (`app/utils/demoClock.ts`) and uses it for "3 minutes ago", call durations and the
  waiting time in the hand-off tray; it never trusts the browser clock for business time. `GET /auth/session` and
  `GET /auth/me` also return `clock: { today, now, demo, timezone }`.
- Every response carries `X-Request-ID` (echoed when the client sends a well-formed one), the security headers in
  `api/middleware.py`, and API responses `Cache-Control: no-store`. SSE responses send `Cache-Control: no-cache,
  no-transform` and `X-Accel-Buffering: no`.
- Anything a caller said is **untrusted text**. The web app renders transcript text, slot values, summaries and
  photo captions as plain text only (no HTML, no markdown, no autolinks). Card numbers are already removed
  (`[card number removed]`) before anything is stored or sent.

### Errors: RFC 7807
Every error is `application/problem+json` (`claimvoice/platform/errors.py`):
```json
{ "type": "https://claimvoice.dev/problems/validation_error", "title": "Validation failed", "status": 422,
  "code": "validation_error", "detail": "One or more fields are invalid.",
  "errors": [{ "field": "reason", "message": "Give a reason for the change." }], "requestId": "…" }
```

| Status | `code` | When |
|---|---|---|
| 400 | `bad_request` | malformed JSON or query |
| 401 | `not_authenticated`, `session_expired`, `invalid_credentials` | no or ended session; wrong email/password (generic) |
| 401 | `invalid_call_token` | caller-leg endpoint without a valid `callerToken` |
| 403 | `forbidden` | permission missing (never reveals other tenants' data) |
| 403 | `csrf_failed` | unsafe method without a valid `X-CSRF-Token` |
| 403 | `no_active_org` | signed in but no active organisation |
| 404 | `not_found` | unknown id **or another org's id** (never 403 for cross-tenant ids) |
| 409 | `call_not_live` | supervisor action on a call that has ended |
| 409 | `already_taken` | hand-off already accepted by someone else; call already taken over |
| 409 | `not_taken_over` | `/say` or `/return` by someone who is not the person on the call ("Take over the call first") |
| 409 | `already_decided`, `already_signed`, `stale_version`, `last_admin`, `gates_failed` | state conflicts (per endpoint) |
| 410 | `expired` | invitation or photo link past its expiry |
| 413 | `payload_too_large` | JSON body over 256 KB; photo over 10 MB |
| 415 | `unsupported_media_type` | photo not JPEG, PNG or WebP. HEIC is refused with a plain message: there is no offline HEIC decoder, so its location data could not be removed (the phone page converts to JPEG first) |
| 422 | `validation_error`, `weak_password`, `invalid_transition` | field errors |
| 429 | `rate_limited` | with `Retry-After` seconds |
| 500 | `internal_error` | logged with the request id |
| 503 | `line_busy`, `unavailable` | all demo lines in use (max 4 live browser calls); a dependency down, with `Retry-After` |

### Pagination
List endpoints marked *(paged)* accept `?page=1&pageSize=25` (max 100) and return
`Page<T> = { items: T[], page, pageSize, total, totalPages }`. Filters are query parameters; a filter named
`status` also accepts `all`. Default order is stated per endpoint.

### Rate limits
Sliding per minute, per IP: `auth` 10 (login, signup, refresh, invitation accept, demo sign-in), `public` 20 (photo
links, public demo call: at most 3 new calls per IP per 10 minutes), `api` 300. Health, metrics and SSE streams are
exempt. Over the limit: `429 rate_limited` with `Retry-After`. Sign-in pauses one email for 15 minutes after 5
failures.

## 1.2 Auth and session: cookie + CSRF

- `cv_session`: opaque random token, httpOnly, `SameSite=Lax`, `Secure` in production; stored server-side as an
  HMAC. **Idle expiry 30 min, absolute 12 h**, on the real wall clock (never the demo clock).
- `cv_csrf`: readable cookie. Echo it in **`X-CSRF-Token`** on every POST/PUT/PATCH/DELETE (also login, signup and
  `POST /demo/calls`). `GET /auth/csrf` sets it. Caller-leg endpoints (§1.6, Part 4) use `Authorization: Bearer
  <callerToken>` instead, and the photo-link upload carries its token in the URL; both are exempt from CSRF.
- Flow: `GET /auth/csrf` → `POST /auth/login` (or `POST /auth/demo`) → use the app. The client calls
  `POST /auth/refresh` at most every 5 minutes while the user is active. On `401 session_expired` the app goes to
  sign-in and returns to the current route afterwards.
- Passwords: Argon2id; at least 12 characters, not common, not containing the email name (`422 weak_password`).
- All auth events are audited (`auth.login`, `auth.login_failed`, `auth.logout`, `auth.password_changed`).

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/auth/csrf` | – | `204` + `cv_csrf` cookie |
| GET | `/auth/session` | – | `SessionState { me: Me \| null, clock }`: **always 200**, so public pages never see a 401 |
| POST | `/auth/signup` | `SignupIn { email, password, fullName, orgName, preferredLanguage }` | `201 Me` (new org, `admin` membership) |
| POST | `/auth/login` | `LoginIn { email, password }` | `Me` |
| POST | `/auth/demo` | `DemoSignInIn { role }` | `Me`: signs in as the sample org's person for that role. Only when the sample org exists and `ENVIRONMENT != production`; else `404` |
| POST | `/auth/logout` | – | `204` |
| POST | `/auth/refresh` | – | `RefreshOut { expiresAt, absoluteExpiresAt }` |
| GET | `/auth/me` | – | `Me` |
| POST | `/auth/switch-org` | `{ orgId }` | `Me` |
| POST | `/auth/password` | `{ currentPassword, newPassword }` | `204` (other sessions ended) |

```text
User         = { id, email, fullName, preferredLanguage: "en"|"fr", avatarColor, createdAt }
Org          = { id, name, slug, timezone, regions: string[], languages: ("en"|"fr")[], isSample, createdAt }
OrgSummary   = { id, name, slug, role, roleLabel, isSample }
Me           = { user, activeOrg: Org|null, membership: { role, roleLabel, title, permissions: string[] }|null,
                 orgs: OrgSummary[], session: { expiresAt, absoluteExpiresAt },
                 clock: { today: "YYYY-MM-DD", now, demo: boolean, timezone } }
```

## 1.3 Roles and permissions

Source of truth: `backend/claimvoice/platform/permissions.py` (unit-tested). Every endpoint below names its
permission. The web app hides what `membership.permissions` does not include; the API enforces it regardless.

| `role` | Label | Who (seeded person) | Lands on |
|---|---|---|---|
| `admin` | Administrator | Claims operations: people, settings, audit (Nadia Kassem) | `/settings` |
| `supervisor` | Claims supervisor | Runs the line desk: listens, whispers, takes over, reviews quality, changes routes, signs routing checks for claims (Renée Kowalchuk) | `/lines` |
| `intake_agent` | Intake agent | Takes hand-offs and calls the line passes over (Jamal Haddad, Sofía Herrera, Aurélie Fortin) | `/lines` |
| `adjuster` | Adjuster | Works claims after the call; may change the route with a reason (Lena Ortiz) | `/claims` |
| `siu_investigator` | Special investigator | Reviews closer-look referrals (Dev Malhotra) | `/claims?route=special_investigation` |
| `compliance` | Compliance and quality | Quality reviews, audit, routing-check sign-off for model risk, privacy officer (Priya Sandhu; Owen Fairweather for call quality) | `/routing` (Priya), `/quality` (Owen) |

| Permission | admin | supervisor | intake_agent | adjuster | siu_investigator | compliance |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `lines:read`, `calls:read`, `claims:read`, `policies:read`, `settings:read`, `members:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `calls:start` | ✓ | ✓ | ✓ | | | |
| `lines:manage` (surge: standby team, surge questions) | | ✓ | | | | |
| `calls:handoff`, `calls:takeover`, `calls:hangup` | | ✓ | ✓ | | | |
| `calls:listen`, `calls:whisper` | | ✓ | | | | |
| `claims:edit` | | ✓ | ✓ | ✓ | | |
| `claims:assign` | ✓ | ✓ | | | | |
| `claims:route` | | ✓ | | ✓ | | |
| `recordings:read` | | ✓ | ✓ | ✓ | ✓ | ✓ |
| `siu:read` | | | | | ✓ | ✓ |
| `siu:decide` | | | | | ✓ | |
| `qa:read` | ✓ | ✓ | | | | ✓ |
| `qa:review` | | ✓ | | | | ✓ |
| `models:read` (routing checks) | ✓ | ✓ | | ✓ | ✓ | ✓ |
| `models:signoff` (supervisor signs for claims, compliance for model risk) | | ✓ | | | | ✓ |
| `settings:manage`, `members:manage`, `org:manage` | ✓ | | | | | |
| `audit:read` | ✓ | | | | | ✓ |

Rules that are not just permissions: closer-look scores and signs (`signs`, `fraud`) and `siu_signal` flags are
stripped from every
response for users without `siu:read` (fields become `null` / omitted, `siuOpen` is `false`). Nobody can approve or
deny a claim in ClaimVoice; routing only decides who looks first.

## 1.4 Organisation, members, invitations

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/org` | members:read | – | `Org` |
| PATCH | `/org` | org:manage | `{ name?, timezone?, languages? }` | `Org` |
| GET | `/org/members` | members:read | – | `Member[]` (name order) |
| PATCH | `/org/members/{membershipId}` | members:manage | `{ role?, title? }` | `Member` (`409 last_admin` when removing the last admin role) |
| DELETE | `/org/members/{membershipId}` | members:manage | – | `204` (`409 last_admin`) |
| GET | `/org/invitations` | members:manage | – | `Invitation[]` |
| POST | `/org/invitations` | members:manage | `{ email, role }` | `201 Invitation` (`acceptUrl` only in development / sample org) |
| DELETE | `/org/invitations/{id}` | members:manage | – | `204` |
| GET | `/invitations/{token}` | public | – | `InvitationPreview { orgName, email, roleLabel, expiresAt }` (`410 expired`) |
| POST | `/invitations/{token}/accept` | public | `{ fullName, password }` | `Me` (signs in) |
| GET | `/roles` | members:read | – | `RoleInfo[] { role, label, description, permissions }` |

```text
Member     = { membershipId, userId, fullName, email, role, roleLabel, title, avatarColor, joinedAt, lastActiveAt, isYou }
Invitation = { id, email, role, roleLabel, invitedBy, createdAt, expiresAt, status: pending|accepted|revoked|expired, acceptUrl? }
```
Invitations expire after 7 days (real clock). Audited: `member.role_changed`, `member.removed`, `invitation.*`.

## 1.5 Policies and policyholders

| Method | Path | Permission | Response |
|---|---|---|---|
| GET | `/policies` *(paged)* | policies:read | `PolicySummary` — filters `q` (number or holder name), `line`, `region`, `status`; order policy number |
| GET | `/policies/{id}` | policies:read | `Policy` |
| GET | `/policyholders` *(paged)* | policies:read | `PolicyholderSummary` — filters `q`, `region`; order name |
| GET | `/policyholders/{id}` | policies:read | `Policyholder` |

```text
PolicySummary = { id, policyNumber, holderId, holderName, line: "auto"|"property", lineLabel ("Auto"|"Home"),
                  productLabel ("Auto Plus"), region, regionLabel, status: active|lapsed|cancelled, statusLabel,
                  effectiveFrom, effectiveTo, openClaims }
Policy        = PolicySummary + { coverages: Coverage[], insuredItems: InsuredItem[], premium, currency,
                  coverageChangedAt: date|null, recentClaims: ClaimSummary[], isSample }
Coverage      = { key ("collision", "comprehensive", "liability", "dwelling", "sewer_backup", "overland_water", …),
                  label, included, limit, deductible, currency }
InsuredItem   = { id, kind: "vehicle"|"property", label ("2021 Toyota RAV4"), details: {…} }
PolicyholderSummary = { id, fullName, phoneMasked ("•••-•••-0142"), emailMasked, city, region, regionLabel,
                        preferredLanguage, policies, claims36m }
Policyholder  = PolicyholderSummary + { postalCodeMasked ("T3J •••"), customerSince, policyList: PolicySummary[],
                  claims: ClaimSummary[], createdAt }
```
Personal data is masked in lists and detail alike; the full phone number is only used server-side for the photo
link. Date of birth is never returned.

## 1.6 Calls

A call is one conversation on the line, live or finished. While live, the voice runtime owns its state; everything
here is what the platform has persisted from `CallSink` (Part 3), so it is consistent with the SSE streams.

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/calls/live` | lines:read | – | `LiveLine[]` (line order) — filter `region` (`CA-AB`, `US-CO`, `CA-QC`: the region pills) |
| GET | `/calls` *(paged)* | calls:read | – | `CallSummary` — filters `status` (`live`, `ended`, `all`), `from`, `to`, `language`, `lossType`, `flag`, `outcome`, `q` (reference, caller, claim number); newest first |
| POST | `/calls` | calls:start | `StartCallIn` | `201 StartCallOut { call: CallDetail, connect: ConnectInfo }` |
| POST | `/demo/calls` | public | `StartCallIn` | `201 StartCallOut`: the landing page's "Ring the demo line" (`/call`). Sample org only, max 6 minutes, rate-limited. The call shows live on the sample line desk, but **nothing is kept after it ends** ("Nothing you say is kept after you close the page"): no recording, no claim; transcript and claim slip are deleted 10 minutes after the end screen. `503 line_busy` when 4 browser calls are live |
| GET | `/calls/{id}` | calls:read | – | `CallDetail` |
| GET | `/calls/{id}/transcript` | calls:read | – | `Transcript` |
| GET | `/calls/{id}/claim-file` | calls:read | – | `ClaimFile` |
| GET | `/calls/{id}/timeline` | calls:read | – | `CallEvent[]` (time order) |
| GET | `/calls/{id}/messages` | calls:read | – | `SmsMessage[]` (texts sent during the call; the sample org shows the photo link so the demo can open it) |
| GET | `/calls/{id}/stream` | calls:read | – | SSE, per-call events (§1.8) |
| GET | `/calls/{id}/recording` · `/calls/{id}/recording/audio` | recordings:read | – | `Recording` / audio, as for claims (§1.7): calls without a claim still play on the quality review page |
| POST | `/calls/{id}/handoff` | calls:handoff | `HandoffIn { reason, toUserId?, team? }` | `HandoffInfo`: hand off from the dock: to a person or a team (`intake` default, `adjusters`, `siu`) with a one-line reason; the call moves into the tray with its summary |
| POST | `/calls/{id}/handoff/accept` | calls:handoff | – | `HandoffAcceptOut { handoff: HandoffInfo, listen: ListenOut }` (`409 already_taken`) |
| POST | `/calls/{id}/listen` | calls:listen | – | `ListenOut` (starts listening; audited) |
| DELETE | `/calls/{id}/listen` | calls:listen | – | `204` |
| POST | `/calls/{id}/whisper` | calls:whisper | `WhisperIn { text }` (≤ 280) | `202 WhisperOut { id, at }` — **a typed note that ClaimVoice acts on** at its next turn (e.g. "Ask if the garage skylight is damaged too"); **the caller never hears it**. It appears in the staff transcript as a `whisper` row ("Whisper, ClaimVoice only") |
| POST | `/calls/{id}/takeover` | calls:takeover | – | `TakeoverOut { call, connect }`: ClaimVoice stops talking and keeps taking notes; `connect` is a send-receive leg so the person's microphone reaches the caller (`409 already_taken`) |
| POST | `/calls/{id}/say` | calls:takeover | `SayIn { text }` | `202 { turnId }` — typed take-over (no microphone): spoken to the caller in the line's voice as the person |
| POST | `/calls/{id}/return` | calls:takeover | – | `CallDetail` — hands the call back to the line, which resumes the interrupted stage |
| POST | `/calls/{id}/hangup` | calls:hangup **or** caller token | `HangupIn { reason, note? }` | `CallDetail` |
| POST | `/calls/{id}/webrtc/offer` | caller token | `SdpOffer` | `SdpAnswer` (Part 4) |
| PATCH | `/calls/{id}/webrtc/ice` | caller token | `IcePatch` | `204` |
| WS | `/calls/{id}/ws?token=…` | caller token | – | fallback transport (Part 4) |

Every supervisor action is audited (`call.listen`, `call.whisper`, `call.handoff_accepted`, `call.takeover`,
`call.returned`, `call.hangup`) and appears in the call timeline.

```text
StartCallIn  = { mode: "voice"|"browser_speech"|"typed" = "browser_speech", language: "en"|"fr"|"auto" = "auto",
                 callerPhone?: E.164 (demo: where the photo link is "texted"; fake SMS),
                 region?: "CA-AB"|"US-CO"|"CA-QC"|"US-CA"|… (decides the consent rule until the policy is found),
                 scenario?: "calgary-windstorm"|"denver-rear-end"|"montreal-basement" (scripted caller plays itself) }
ConnectInfo  = { callId, callerToken, offerUrl, iceUrl, websocketUrl, dataChannelLabel: "claimvoice",
                 iceServers: { urls[], username?, credential? }[], maxSeconds }

LiveLine     = { callId, lineLabel ("Line 1"), state, stateLabel, stage: StageInfo, mode, language, callerLabel
                 ("Gord Lindqvist" | "Unverified caller"), callerVerified, callerPhoneMasked, region, regionLabel,
                 place ("Saddle Ridge, Calgary"), lossType, lossTypeLabel ("Wind"), answeredAt, flags: Flag[],
                 mood: { key: calm|unsettled|shaken|upset, label ("Sounds shaken"), detail ("speaking slower")|null },
                 heard: { key, text ("Skylight smashed by debris"), tone: normal|caution ("Sore neck") }[] (≤ 4),
                 lastAsked: { text, textEn|null }|null ("ClaimVoice asked: '…'"; English under French lines),
                 handoff: HandoffInfo|null, listeners: Listener[], inSurge, claimFileProgress (0..1), isSample }
  state       ringing | with_line | waiting_for_person | with_person | wrapping_up | ended
StageInfo    = { key (Part 5 stage), label, step (1..7), stepLabel ("What happened"), steps (7),
                 nextLabel ("Photos next") }   → "Step 4 of 7 · What happened" on the script track
Flag         = { kind, label, detail, severity: info|warning|critical, at, turnId? }
  kind        urgent_safety | distress | card_number_removed | low_confidence | siu_signal (siu:read only) |
              consent_refused | surge | language_switched
Listener     = { userId, name, mode: listening|took_over }
HandoffInfo  = { id, callId, reason, reasonLabel ("Urgent safety", "Asked for a person"), detail ("Smells gas after the
                 wind tore the cover off his gas meter."), priority: urgent|high|normal,
                 state: waiting|accepted|completed|returned_to_line|callback_offered, requestedAt, waitingSeconds,
                 acceptedBy: { id, name }|null, acceptedAt, callerLabel, lineLabel, place ("Airdrie"), lossTypeLabel,
                 language, summary (two lines: "Read the summary"), actionsTaken: string[] ("Told him to leave the
                 house and call 911"), to: { id, name }|null, team: intake|adjusters|siu|null }
  reason      caller_asked | urgent_safety | distress | low_confidence | identity_unverified | tool_failed |
              consent_refused | supervisor
  priority    urgent_safety → urgent; distress, identity_unverified → high; otherwise normal

CallSummary  = { id, reference, startedAt, endedAt, durationSeconds, state, stateLabel, mode, language, callerLabel,
                 regionLabel, lossTypeLabel, outcome: claim_created|handed_off|abandoned|no_claim|in_progress,
                 outcomeLabel, claimId, claimNumber, flags, qaScore, isSample }
CallDetail   = CallSummary + { lineLabel ("Line 1", while live) | null, place | null, stage: StageInfo, stages: StageInfo[] (the scripted path), consent: Consent,
                 policyId, policyNumber, holderId, handoff, listeners, summary, summaryEn, recordingAvailable,
                 surgeId }
Consent      = { rule: one_party|all_party, ruleLabel ("All-party consent (California)"), region,
                 answer: given|refused|not_required|pending, answerLabel, recording: boolean, askedAt, turnId }

Transcript   = { callId, language, retained: boolean, notice: string|null, turns: Turn[] }
Turn         = { id, seq, speaker: caller|line|person|system|whisper, speakerLabel ("Gord Lindqvist", "ClaimVoice",
                 "Renée Kowalchuk", "Whisper, ClaimVoice only · Renée"), text, textEn (English line under French
                 turns, for staff; null on English calls), language, atMs, endMs, stage,
                 confidence, interrupted, redactions, flags: FlagKind[] }
  whisper rows are staff-only: they are never sent on the caller's data channel

ClaimFile    = { callId, claimId, lossType, lossTypeLabel, progress (0..1), missing: string[] (labels),
                 sections: { key: caller|policy|loss|details|safety|photos|coverage|next_steps, label, slots: Slot[] }[] }
Slot         = { key, label, value, display ("Thursday 8 January, about 2:30 a.m."), confidence, confidenceLabel:
                 sure (≥0.85) | likely (≥0.6) | check, source: heard|policy_record|tool|person, sourceLabel (the
                 source chip: "▸ 1:52", "from the policy", "looked up", "edited by Lena Ortiz"),
                 span: { turnId, start, end } | null, heardAtSeconds (the ▸ moment), changedAtSeconds ("Changed at
                 3:12" when the caller corrected it), confirmed, required, history: SlotHistory[] }
SlotHistory  = { value, display, source, changedBy, at, span, note }
CallEvent    = { id, at, atMs, kind, label ("Policy found in 0.2 s", "Renée Kowalchuk started listening"), actor, data }
  kind        answered | consent | identity | stage | tool | flag | handoff | listen | whisper | takeover | returned |
              photo_link | read_back | notice | ended
  data        the call-quality scorer reads: answered {region, language}; consent {rule, answer, recording, region};
              identity {verified}; stage {stage, previous, event}; flag {kind, detail, turnId}; handoff {reason,
              priority, state: requested|accepted}; read_back {confirmed}; ended {reason}
ListenOut    = { mode: "audio"|"transcript", connect: ConnectInfo|null }   (the dock's "line you are on" player)
TakeoverOut  = { call: CallDetail, connect: ConnectInfo|null }
SmsMessage   = { id, toMasked, body, sentAt, status }
```

**Transcript-span links.** `Slot.span` points into `Turn.text` of `span.turnId` with character offsets
`[start, end)` in the stored (redacted) text. The web app highlights that range and scrolls to it; a corrected value
keeps the old span in `history`. `policy_record` and `tool` values have no span.

**Consent refused.** Recording stops; from then on only notes are kept. `Transcript.retained=false`, `turns=[]`,
`notice="Recording stopped at the caller's request. Notes only from here."` The claim file is kept (it is the claim).
In all-party regions nothing is kept before the caller says yes.

### Photo links (public, for the caller's phone)

| Method | Path | Response |
|---|---|---|
| GET | `/photo-links/{token}` | `{ orgName, claimReference, language, expiresAt, maxPhotos (10), uploaded }` (`410 expired` after 72 h) |
| POST | `/photo-links/{token}/photos` | multipart `file` (+ `caption?`) → `201 Photo`; JPEG/PNG/HEIC/WebP ≤ 10 MB; EXIF location removed |

The web route is `/p/{token}` (mobile-first page). Uploads appear on the claim and raise `claim.updated` on the
switchboard stream.

## 1.7 Claims

A claim is created by the platform when a call closes with a loss reported (Part 3, "At hang-up").

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/claims` *(paged)* | claims:read | – | `ClaimSummary` — filters `status`, `route`, `lossType`, `line`, `region`, `assigned` (`me`, `none`, userId), `flag` (`urgent_safety`, `siu`), `surge` (id), `from`, `to`, `q`; newest first |
| GET | `/claims/{id}` | claims:read | – | `Claim` |
| PATCH | `/claims/{id}` | claims:edit | `{ status }` | `Claim` |
| POST | `/claims/{id}/assign` | claims:assign | `{ userId \| null }` | `Claim` |
| GET | `/claims/{id}/transcript` | claims:read | – | `Transcript` |
| PATCH | `/claims/{id}/file` | claims:edit | `FileEditIn { slots: [{ key, value, note }] }` | `ClaimFile` (keeps the heard value in `history`) |
| GET | `/claims/{id}/recording` | recordings:read | – | `Recording` |
| GET | `/claims/{id}/recording/audio` | recordings:read | – | `audio/ogg` (Opus) or `audio/wav`, supports `Range` |
| GET | `/claims/{id}/photos` | claims:read | – | `Photo[]` |
| GET | `/photos/{id}` · `/photos/{id}/thumbnail` | claims:read | – | image |
| GET | `/claims/{id}/routing` | claims:read | – | `RoutingDecision` ("Where it goes") |
| POST | `/claims/{id}/routing/accept` | claims:route | – | `RoutingDecision` ("Accept route"; audited) |
| POST | `/claims/{id}/routing/override` | claims:route | `{ route, reason }` | `RoutingDecision` ("Change with a reason"; reason required; audited) |
| GET | `/claims/{id}/siu` | siu:read | – | `SiuReferral` (`404` when none) |
| POST | `/claims/{id}/siu/decision` | siu:decide | `{ decision: investigate\|close_no_concern\|return_to_adjuster, note }` | `SiuReferral` (audited) |
| GET | `/siu/referrals` *(paged)* | siu:read | – | `SiuReferral` — filter `status`; open first, then newest |

```text
ClaimSummary = { id, claimNumber ("CV-26-01856"), status: new|assigned|in_review|waiting_on_customer|closed,
                 statusLabel, line, lossType, lossTypeLabel, lossDate, lossPlace ("Saddle Ridge, Calgary"), holderName,
                 policyNumber, regionLabel, language, reportedAt,
                 route: { route, label, decidedBy: model|person, topReason } | null,
                 urgentSafety, siuOpen ("Closer look" tag), photos, assignedTo: { id, name }|null,
                 surgeLabel ("Chinook windstorm, Calgary"), isSample }
Claim        = ClaimSummary + { callId, policyId, holderId, description, descriptionEn, flags, file: ClaimFile,
                 inShort: { text, links: { start, end, turnId, atSeconds }[] (heard phrases underlined),
                            checkedBy, checkedAt } ("In short · checked by Lena at 5:40"),
                 nextSteps: string[], recordingAvailable }
Recording    = { available, reason ("The caller did not agree to recording" | "Removed after 90 days"), audioUrl,
                 durationSeconds, peaks: number[] (~800, 0..1, for wavesurfer.js), retainedUntil,
                 segments: { turnId, speaker, startSeconds, endSeconds, paused }[] (one wavesurfer region per turn),
                 moments: { kind: consent|policy|safety|sign|photos|read_back|claim_number|handoff|whisper, label,
                            atSeconds, turnId }[] (pins above the lanes),
                 hushes: [startSeconds, endSeconds][] (card-number cuts, drawn hatched) }
Photo        = { id, url, thumbnailUrl, caption, receivedAt, source: text_link|uploaded_by_staff, width, height }
RoutingDecision = { claimId, route (effective), routeLabel, modelRoute, decidedAt,
                 severity: { probability, band: small|moderate|large, label ("Likely size: Moderate"),
                             detail ("Claims like this usually settle at $4,000 to $9,000"),
                             settleRange: { low, high, currency } } (the size check),
                 fraud: { probability, band: low|elevated|high, label, detail } | null (siu:read only),
                 reasons: { feature, text, direction: raises|lowers, weight, turnId, atSeconds }[] (3, plain words:
                           "Why an adjuster, not fast-track", each with its ▸ moment when heard),
                 signs: SiuIndicator[] | null (siu:read only: "Signs worth a closer look"), signsChecked (14: "3 of the
                 14 we check"), rulesApplied: string[] ("A possible injury is never fast-tracked"),
                 modelVersions: { size, closerLook }, acceptedBy, acceptedAt,
                 override: { route, reason, by, at } | null,
                 statement: "For a person to review. A sign is never a reason to deny a claim on its own, and nothing
                             here was decided automatically." }
  route       fast_track ("✓ Fast-track") | adjuster ("Adjuster") | special_investigation ("Closer look")
  A claim can show two route tags: its route (who works it first) and an open closer-look referral (`siuOpen`).
SiuIndicator = { key, label ("Policy started 19 days before the loss"), evidence, source: call|policy|claim_history|
                 weather, sourceLabel ("▸ 2:41", "from the policy", "claim history"), turnId, atSeconds, weight }
SiuReferral  = { id, claimId, claimNumber, status: open|investigating|closed_no_concern|returned_to_adjuster,
                 statusLabel, openedAt, score, indicators: SiuIndicator[],
                 decidedBy, decidedAt, note,
                 statement: "A referral is a request for review. It is not a finding of fraud and never denies a claim." }
```

## 1.8 The line desk (supervisor switchboard) and live updates (SSE)

| Method | Path | Permission | Response |
|---|---|---|---|
| GET | `/switchboard` | lines:read | `SwitchboardSnapshot` |
| GET | `/switchboard/stream` | lines:read | SSE, org-wide events |
| GET | `/calls/{id}/stream` | calls:read | SSE, one call's events (open while the call page is open) |
| GET | `/surges` | lines:read | `Surge[]` (active first) |
| GET | `/surges/{id}` | lines:read | `Surge` |
| POST | `/surges/{id}/standby` | lines:manage | `{ note? }` → `Surge` ("Bring in the standby team (2)": the standby people become available for hand-offs; audited) |
| POST | `/surges/{id}/questions` | lines:manage | `{ on }` → `Surge` ("✓ Wind questions switched on": the loss type's surge questions are added to new calls in the area; audited) |

```text
SwitchboardSnapshot = { caption ("Larkspur Mutual · Thursday 8 January · 7:42 a.m. Calgary time · 3 on the line,
                        2 waiting for a person"), lines: LiveLine[] (not waiting for a person),
                        handoffTray: HandoffInfo[] (urgent first, then oldest first),
                        freePeople: { id, name }[] ("Jamal, Sofía and Aurélie are free to take calls"),
                        surge: Surge|null, recentClaims: ClaimSummary[] ("Finished this morning", newest first, ≤ 8),
                        today: TodayStats, lastEventId }
TodayStats   = { callsAnswered, answeredFirstRingShare (0..1), medianHandleSeconds, handoffs, claimsCreated,
                 averageQaScore, surgeCalls }   (org-local today, demo clock)
Surge        = { id, kind: hail|flood|wind|winter_storm|rainfall|wildfire, kindLabel, title ("Chinook windstorm,
                 Calgary"), headline ("Gusts over 100 km/h overnight: roofs, fences and siding"), region, regionLabel,
                 areaLabel ("Calgary and Airdrie"), startedAt, endedAt, active,
                 source ("Environment and Climate Change Canada wind warning (bundled snapshot)"), callsLastHour,
                 usualCallsPerHour, multiplier (3.4: "Calls are 3.4× usual since 6 a.m."), sinceLabel ("since 6 a.m."),
                 surgeQuestionsOn ("✓ Wind questions switched on"), waitForPersonSeconds ("◷ Wait for a person: about
                 1 min"), standbyAvailable (2), standbyCalled, policiesInArea, claimsSoFar,
                 guidance ("What's covered": "Wind damage to roofs, siding and skylights is covered under Home
                 Comprehensive; fences up to $5,000.") }
```

**SSE framing.** `id: <int>` (per-org, increasing), `event: <type>`, `data: <Envelope JSON>`;
`Envelope = { type, at, orgId, callId|null, data }`. The server sends `event: ping` every 15 s. Reconnect with
`Last-Event-ID`; events from the last 5 minutes are replayed, older gaps get `event: resync` (reload the snapshot).
Events respect permissions: `siu_signal` flags and fraud fields are removed for subscribers without `siu:read`.
The first frame of every stream is `retry: 3000` (always an integer). Payload labels are English; codes are always
present, so a French page refetches the REST item (or the snapshot) for its labels. Live captions (`turn.partial`)
carry no `id` and are never replayed. Live-strip waveforms are drawn by the web app from turn timing (the caller's
browser speaks the line in the default mode, so the server has no level for it).

Org stream (`/switchboard/stream`):

| `type` | `data` |
|---|---|
| `line.opened` · `line.updated` | `LiveLine` (any change: stage, flags, caller verified, listeners, hand-off) |
| `line.closed` | `{ callId, outcome, outcomeLabel, claimId, claimNumber }` |
| `handoff.requested` · `handoff.updated` | `HandoffInfo` |
| `surge.started` · `surge.updated` · `surge.ended` | `Surge` |
| `claim.created` · `claim.routed` · `claim.updated` | `ClaimSummary` |
| `qa.flagged` | `QaQueueItem` (a call scored "failed" or with a critical item failed) |
| `stats.updated` | `TodayStats` (at most every 10 s) |
| `resync` | `{}` |

Per-call stream (`/calls/{id}/stream`):

| `type` | `data` |
|---|---|
| `turn.partial` | `{ speaker: "caller", text }` (live caption; never stored) |
| `turn.final` | `Turn` |
| `slot.updated` | `{ slot: Slot, progress }` |
| `stage.changed` | `StageInfo` |
| `flag.raised` | `Flag` |
| `handoff.updated` | `HandoffInfo` |
| `whisper.sent` | `{ id, text, by, at }` |
| `listener.changed` | `{ listeners: Listener[] }` |
| `tool.called` | `{ tool, label ("Policy found"), elapsedMs, ok }` |
| `notice` | `{ kind, text }` (same kinds as Part 4 `call.notice`) |
| `call.ended` | `{ reason, claimId, claimNumber }` |

## 1.9 Call quality (`/quality`)

Every finished call is scored automatically against the rubric (`backend/claimvoice/qa/rubric.py`): rules over the
transcript, events and claim file, plus a language check through the language-understanding adapter (fake by
default). Calls go to the review queue when a critical item fails, the score is under 70, a hand-off rule applied, or
by a random 10 % sample.

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/qa/rubric` | qa:read | – | `RubricItemInfo[] { key, label, description, points, critical, bead }` |
| GET | `/qa/queue` *(paged)* | qa:read | – | `QaQueueItem` — filters `status` (`needs_review` default, `reviewed`, `auto_passed`, `all`), `item` (rubric key: the filter pills Missed consent = `consent_first`, Late hand-off = `handoff_correct`, Card number = `no_card_numbers`, Low details = `required_fields`), `band`, `from`, `to`; flagged first, then lowest score |
| GET | `/qa/calls/{callId}` | qa:read | – | `QaScore` |
| POST | `/qa/calls/{callId}/review` | qa:review | `ReviewIn { items: [{ key, verdict: agree\|disagree, note? }], note?, coachingNote? }` | `QaScore` (audited; the coaching note goes to the script owner) |
| GET | `/qa/agreement` | qa:read | – | `Agreement { reviewedCalls, overall, cohenKappa, byItem: [{ key, label, reviewed, agreement }] }` |

```text
Bead         = { key, label, passed: boolean|null, detail ("9/10") }   six per call, in rubric order:
               Consent first · Identity checked · Required details · Kind words · No card numbers · Right hand-off
QaScore      = { callId, claimId | null, claimNumber, score (0..100), band: good (≥85) | needs_attention (≥70) | failed, bandLabel,
                 status: needs_review|reviewed|auto_passed, items: QaItem[], beads: Bead[],
                 focus: { atSeconds, text ("Jumped to 4:10, where the hand-off came 40 seconds late") } | null,
                 scoredAt, scorerVersion, reviewedBy, reviewedAt, reviewNote }
QaItem       = { key, label, passed: boolean|null (null = not applicable), points, maxPoints, critical,
                 method: rule|language_check, note, evidence: { turnId, quote }[], atSeconds (where the bead pins on
                 the recording), reviewerVerdict, reviewerNote }
QaQueueItem  = { callId, reference, claimId | null, claimNumber, callerLabel, lineLabel, startedAt, durationSeconds, language,
                 lossTypeLabel, score, band, bandLabel, beads: Bead[], failedItems: string[], status,
                 reasonQueued ("Critical item failed: safety asked"), reviewer: { id, name }|null }
```
Rubric keys: `consent_first`, `consent_rule`, `identity_verified`, `required_fields`, `safety_check`, `read_back`,
`empathy`, `no_card_numbers`, `handoff_correct`, `language_honoured`, `no_promises`. A failed critical item makes the
band `failed` whatever the score. Empty queue copy: "Nothing to review. Every call this week met the rubric."

## 1.10 Routing checks (`/routing`)

Two checks run when a call ends: the **size check** (`size`: "How big is this claim likely to be?", decides fast-track
or adjuster) and the **closer-look check** (`closer_look`: "Should someone in special investigations look at it?",
never denies). Internally they are the severity and fraud-indicator models (Part 6). The page answers the four
questions a regulator asks, in frequencies ("96 in 100"), with one chart each; technical metrics live in each fact
sheet's "for the technical reviewer" fold. Shapes: `schemas/ml.py`.

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/routing-checks` | models:read | – | `RoutingChecks { caption, checks: Check[], questions: Question[] (right, fair, like_learned, replace), never: string[] }` |
| GET | `/routing-checks/{check}` | models:read | – | `FactSheet` (the model card in plain language + `technical` fold + `versions`) |
| GET | `/routing-checks/{check}/fairness?version=` | models:read | – | `Fairness` |
| POST | `/routing-checks/{check}/versions/{version}/sign-off` | models:signoff | `SignOffIn { version, note }` | `Check`. The side follows the role (supervisor → `claims`, compliance → `model_risk`); two different people; `409 already_signed`; `409 gates_failed` when a gate fails. When both sides have signed, the candidate goes into use and the old version is retired (audited) |
| GET | `/routing-checks/regulator-pack` | models:read | – | `application/zip`: both fact sheets (Markdown), fairness and drift tables (CSV), sign-off history and the routing-related audit extract ("Pack for the regulator"; audited) |

```text
Check        = { key: size|closer_look, name ("Size check"), question, decides, inUse: CheckVersion,
                 candidate: CheckVersion|null, status: healthy|watch|act, statusLabel ("Working as expected",
                 "Watch: storm week", "Act"), signedBy }
CheckVersion = { version (int), stage: in_use|candidate|retired, algorithm, inUseSince, trainedOn, metrics: MetricSet,
                 gates: GateResult[], gatesPassed, signOffs: SignOff[2] }
SignOff      = { side: claims|model_risk, sideLabel ("Claims", "Model risk"), by, at, note, state: signed|waiting }
Question     = { key, question, answer (sentence; **…** marks the emphasised phrase), foot,
                 bars?   (right:  [{ label: "Size check", value: 0.96, ours: true }, { label: "Old rule of thumb", 0.81 }]),
                 dots?, overallRate?, band?  (fair: closer-look rate by region, language, age band vs the overall line
                                              and the allowed band, ±0.015 = ±1.5 points),
                 weeks?  (like_learned: 8 weekly columns { label, psi, status } against Watch 0.10 and Act 0.25),
                 compare?, signOffs?  (replace: rows right · investigators agreed · fair across groups · reasons stay
                                       the same, in use vs candidate, and the two sign-offs) }
FactSheet    = { key, name, version, sections: { key: for|not_for|looks_at|never_looks_at|tested|limits|fairness|
                 sign_offs|technical, title, body: string[] }[], technical: { test, baseline, randomForest, roc, pr,
                 calibration, split, features }, versions: CheckVersion[] }
Fairness     = { key, version, overallRate, band, passed, rows: { dimension, group, label, count, flaggedRate,
                 truePositiveRate, falsePositiveRate, gap, withinBand }[],
                 note: "Age, language and region are never used to route a claim. We use them only here, to check
                        fairness." }
```
`never` (the "It never" pills): "denies a claim", "uses age, gender, language or postcode to route", "stops a person
changing the route", "changes version without two sign-offs". Drift at Act pauses fast-track for that check (every
claim goes to an adjuster) until a person resumes it; the page says so. Model cards, metrics and results never include
run timestamps.

## 1.11 Settings (`/settings/{scripts,consent,handoff,languages,retention,people}`)

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| GET | `/settings` | settings:read | – | `SettingsOverview { languages, retention, handoffRules, privacy, consentRules (count), scripts (count) }` |
| GET | `/settings/scripts` | settings:read | – | `Script[]` (one per loss type: Collision · Hail · Wind · Water · Fire · Theft) |
| GET | `/settings/scripts/{lossType}` | settings:read | – | `Script` |
| PUT | `/settings/scripts/{lossType}` | settings:manage | `ScriptIn { questions, note }` | `Script` (new version; audited) |
| GET | `/settings/scripts/{lossType}/preview?language=&index=` | settings:read | – | `audio/wav`: "▸ Hear it" (the question in the line's voice; fake TTS offline, or the browser speaks the text itself) |
| GET | `/settings/consent-rules` | settings:read | – | `ConsentRule[]` (all-party regions flagged ⚖: "nothing is kept until the caller says yes") |
| PUT | `/settings/consent-rules/{region}` | settings:manage | `ConsentRuleIn { rule, announcement: { en, fr } }` | `ConsentRule` (`422` when weakening an all-party region) |
| GET · PUT | `/settings/handoff-rules` | settings:read · settings:manage | `HandoffRules` | `HandoffRules` |
| GET · PUT | `/settings/languages` | settings:read · settings:manage | `Languages` | `Languages` |
| GET · PUT | `/settings/retention` | settings:read · settings:manage | `Retention` | `Retention` |
| GET · PUT | `/settings/privacy` | settings:read · settings:manage | `Privacy` | `Privacy` |

People (`/settings/people`) uses §1.4. The audit log (`/activity`) uses §1.12.

```text
Script         = { lossType, lossTypeLabel, line, version, questions: ScriptQuestion[], updatedAt, updatedBy }
ScriptQuestion = { slotKey, label (the fact it fills), kind: text|date|time|yes_no|phone|number|choice|address|
                   policy_number|money_band, prompt: { en, fr }, required, when ("other_party_involved == true") | null,
                   choices: string[], surgeOnly (asked only while a surge's questions are switched on) }
ConsentRule    = { region, regionLabel, rule: one_party|all_party, ruleLabel, announcement: { en, fr },
                   basis ("California Penal Code §632"), onRefusal ("Recording stops; notes only; a person is offered"),
                   isDefault }
HandoffRules   = { urgentKeywords: string[] (["gas", "smoke", "fire", "someone hurt"]: "If the caller mentions [...],
                   bring in a person now"), askedTimes (1: "If the caller asks for a person [once]"),
                   lowConfidenceTurns (2: "If ClaimVoice isn't sure what it heard [twice in a row], offer a person"),
                   distressThreshold (0.7), identityAttempts (3), offerPersonOnConsentRefusal (true),
                   maxWaitSeconds (90; then a call-back is offered), urgentSafetyAlways (read-only true) }
Languages      = { enabled: ["en","fr"], default, voices: { en: { voice, speed }, fr: { voice, speed } },
                   detectAutomatically, frenchFirstRegions: ["CA-QC"] (French first for Québec numbers) }
Retention      = { recordingsYears (7), transcriptsYears (7), photosYears (7), claimFilesYears (7, read-only),
                   cardNumberMoments: "always_removed" (read-only), refusedConsentTranscripts: "not_kept" (read-only),
                   deletionRequestsWaiting, lastPurgeAt, nextPurgeOn }
Privacy        = { privacyOfficerName, privacyOfficerEmail, privacyNoticeUrl }
```
Changes take effect for calls answered after the change; a live call keeps the script version it started with.

## 1.12 Audit (`/activity`)

| Method | Path | Permission | Response |
|---|---|---|---|
| GET | `/audit` *(paged)* | audit:read | `AuditEntry` — filters `action` (prefix, e.g. `call.`), `actor` (userId), `target` (type:id), `from`, `to`; newest first |
| GET | `/audit/verify` | audit:read | `ChainStatus { ok, checked, firstBrokenSeq, reason, checkedAt }` |
| GET | `/audit/export.csv` | audit:read | CSV of the filtered entries (audited itself) |

```text
AuditEntry = { id, seq, at, actorLabel, action, actionLabel ("took over"), targetType, targetId,
               targetLabel ("Line 1 (Gord Lindqvist)", "CV-26-01856"), summary (one sentence: "Renée Kowalchuk took
               over Line 1 (Gord Lindqvist) at 7:44 a.m."), details }
```
The page groups entries by day, shows "Record intact ✓ · checked 7:40 a.m." from `/audit/verify`, and filters by
person, action and claim.

Audited actions (minimum): `auth.*`, `member.*`, `invitation.*`, `org.updated`, `call.listen`, `call.whisper`,
`call.handoff_accepted`, `call.takeover`, `call.returned`, `call.hangup`, `claim.file_edited`, `claim.assigned`,
`claim.route_accepted`, `claim.route_override`, `claim.status_changed`, `siu.decision`, `qa.review`,
`check.signed_off`, `check.version_in_use`, `check.regulator_pack`, `surge.standby_called`, `surge.questions`, `settings.*`,
`retention.purged`, `recording.played` (who listened to which recording), `audit.exported`.

## 1.13 Reference data, health

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/meta` | public | `Meta { product, version, languages, lossTypes: { key, label, line }[], regions: { code, label, country, consentRule }[], stages, routes, roles, demoScenarios }` (labels in `Accept-Language`) |
| GET | `/health` (no `/api/v1` prefix) | public | `{ status: ok\|degraded, version, database, now, demoClock }` |
| GET | `/metrics` (no prefix) | public on localhost | Prometheus text: request counts and durations, live calls, turn latency histogram, tool timeouts, SSE subscribers |

Loss types (`lossType`, `backend/claimvoice/reference.py`): `collision` "Collision", `hail` "Hail", `wind` "Wind",
`water` "Water", `fire` "Fire or smoke", `theft` "Theft or break-in". A loss type says what happened, not which
policy line; one loss can touch a home and a vehicle (the insured items say which). Routes, check names, regions
with their consent rules and the demo scenarios are in the same module and in `GET /meta`.

---

# Part 2: Data model (SQLAlchemy 2 + Alembic; SQLite default, Postgres-ready)

Migration `0001` (exists) creates the platform tables; `0002` adds the domain tables. Every tenant-owned table has
`org_id` (indexed) and every query filters by the active org; ids are UUID strings; times are `UTCDateTime`.

| Table | Columns (beyond id, org_id, created_at) | Notes |
|---|---|---|
| `organizations` | name, slug, timezone, regions, languages, settings (JSON: hand-off rules, retention, privacy), is_sample | 0001 |
| `users` · `memberships` · `sessions` · `invitations` | see `platform/models.py` | 0001 |
| `audit_events` | seq, at, actor_user_id, actor_label, action, target_type, target_id, summary, details, ip, prev_hash, hash | 0001; unique (org_id, seq) |
| `policyholders` | full_name, phone_e164, email, date_of_birth, postal_code, city, region, preferred_language, customer_since | DOB only for identity checks and age bands |
| `policies` | policy_number (unique per org), holder_id, line, product, region, status, effective_from/to, premium, currency, coverage_changed_at | |
| `coverages` | policy_id, key, included, limit, deductible | |
| `insured_items` | policy_id, kind, label, details (JSON) | |
| `calls` | reference, line_number, mode, channel, language, state, stage, stage_index, resume_stage, answered_at, ended_at, end_reason, caller_phone_e164, caller_name, caller_verified, region, place, loss_type, policy_id, holder_id, consent (JSON), recording_path, recording_seconds, summary, summary_en, outcome, surge_id, scenario, is_sample, is_public_demo, latency_p95_ms, flags / mood / heard / last_asked / listeners (JSON, the live strip), caller_token_hash, claim_number (reserved), facts (JSON: the engine's call facts for the routing checks) | |
| `call_turns` | call_id, seq, speaker, speaker_name, text, text_en, language, at_ms, end_ms, stage, confidence, interrupted, redactions, retained, flags | id = the voice runtime's `turn_id` |
| `call_slots` | call_id, key, value (JSON), display, confidence, source, turn_id, span_start, span_end, at_ms, confirmed, corrects, superseded_at, changed_by, note | current value = latest non-superseded row per key |
| `call_events` | call_id, at, at_ms, kind, label, actor_user_id, data (JSON) | timeline |
| `handoffs` | call_id, reason, detail, priority, state, requested_at, accepted_by, accepted_at, resolved_at | |
| `whispers` | call_id, author_id, text, at, acted_on_turn_id | merged into the staff transcript as `whisper` rows |
| `sms_messages` | call_id, to_e164, body, status, sent_at, provider_id | photo link token inside `photo_links` |
| `photo_links` | call_id, claim_id, token_hash, expires_at, max_photos | |
| `claims` | claim_number, call_id, policy_id, holder_id, line, loss_type, loss_date, loss_place, description, description_en, status, assigned_to, urgent_safety, surge_id, language | |
| `claim_photos` | claim_id (null until the claim exists), call_id, path, thumbnail_path, content_type, caption, width, height, source, received_at | files under `data/uploads/`; photos texted during the call are adopted by the claim at hang-up |
| `routing_decisions` | claim_id, route, model_route, accepted_by, accepted_at, settle_low, settle_high, severity_probability, severity_band, fraud_score, fraud_band, reasons (JSON), fraud_indicators (JSON), rules_applied (JSON), model_versions (JSON), features (JSON snapshot), override_route, override_reason, override_by, override_at | features snapshot = drift and audit |
| `siu_referrals` | claim_id, status, score, indicators (JSON), opened_at, decided_by, decided_at, note | |
| `qa_scores` | call_id, score, band, status, items (JSON), beads (JSON), focus (JSON), scorer_version, scored_at, reviewed_by, reviewed_at, review (JSON), coaching_note | |
| `surges` | kind, region, area_label, title, headline, alert_id, started_at, ended_at, usual_calls_per_hour, surge_questions_on, standby_available, standby_called_at, guidance | |
| `model_versions` | check_key (`size`/`closer_look`), version, stage (in_use/candidate/retired), algorithm, metrics (JSON), gates (JSON), fact_sheet (JSON), trained_by, in_use_since, mlflow_run_id | the registry mirror the API reads |
| `check_signoffs` | model_version_id, side (claims/model_risk), user_id, note, signed_at | unique (model_version_id, side); two different people |
| `scripts` | loss_type, version, questions (JSON, incl. `surgeOnly`), updated_by, note | latest version per loss type is active |
| `consent_rules` | region, rule, announcement (JSON), basis, is_default | shipped defaults seeded per org |

Retention: a daily job (in the API process) deletes recordings, transcripts and photos past their retention, keeps
the claim file, and writes `retention.purged`. Refused-consent turns are deleted when the call closes.

---

# Part 3: Python interfaces between the voice runtime and the platform

Code: `backend/claimvoice/contracts.py` (frozen dataclasses and Protocols; no ORM objects cross the line).

**Ownership.** The voice runtime owns a live call's state in memory and is the **only source of call facts**. The
platform owns the database, the SSE event bus, audit and every HTTP endpoint. **The voice runtime never writes to the
database; the platform never drives the dialogue.**

| Interface | Implemented by | Called by | Purpose |
|---|---|---|---|
| `CallSink` | platform (`calls/sink.py`, `SqlCallSink`) | voice runtime | persist turns, slots, stages, flags, tool timings, consent, hand-off requests, close; publish SSE |
| `LineControl` | voice runtime (`voice/lines.py`, `LineManager`) | platform HTTP handlers | whisper, take over, say as person, hand back, hang up |
| `LineRuntime` (extends `LineControl`) | voice runtime (`get_line_manager()`) | platform HTTP handlers, API start-up | prepare a line, answer the SDP offer, add ICE, run the WebSocket fallback, adopt the seeded live lines, nudge a scripted line when someone listens |
| `PolicyDirectory` | platform (`policies/directory.py`) | dialogue tools | find policy, verify identity, coverage summary, prior claims |
| `OrgPlaybook` | platform (`settings/playbook.py`) | dialogue engine | script per loss type, consent rule per region, hand-off rules, active surge |
| `TriageScorer` | ML (`ml/scorer.py`) | platform at hang-up | route + reasons + closer-look signs (the two routing checks) |
| `CallScorer` | QA (`qa/scorer.py`) | platform at hang-up | rubric score with evidence |
| `SpeechToText`, `TextToSpeech` | voice (`voice/adapters.py`) | pipeline | fakes by default |
| `LanguageUnderstanding`, `LlmClient` | NLU (`nlu/`) | dialogue engine, QA, summaries | fakes by default |
| `SmsSender`, `WeatherFeed` | tools (`tools/`) | dialogue tools | fake outbox, bundled weather |

**Who persists what.**
- Turns: the voice runtime generates `turn_id` (uuid4) and calls `CallSink.turn()` once per **final** turn, after
  redaction. Interim caller text goes to `CallSink.partial()` (SSE only, never stored).
- Slots: `CallSink.slot()` for every new or corrected value, referencing the `turn_id` and span it was heard in. The
  platform appends a `call_slots` row and supersedes the previous one for that key.
- Stage changes, flags, tool calls, consent and latency samples: one `CallSink` call each; the platform writes the
  call row and timeline and publishes `line.updated` / per-call events.
- Ordering: `CallSink` methods are awaited in order on the call's task, so a slot never arrives before its turn.
  Each must return within **20 ms p95**: `SqlCallSink` only updates memory, publishes the per-call event and queues
  the write; one writer task per call drains the queue in order and coalesces `line.updated` for the desk.
- Claim number: `CallSink.reserve_claim_number` returns the number the line reads at wrap-up; the claim created at
  hang-up uses it. `CallClosing.facts` carries the engine's call facts (third-party pressure, weather match, ...),
  stored on the call and passed to the routing checks' feature builder.
- Audio: the voice runtime writes the recording to `RECORDINGS_DIR/{call_id}.wav` (stereo 16 kHz: the caller on the
  left channel, the line or a person on the right; written only after consent; card-number moments silenced) and
  reports the relative path and length in `CallClosing`.

**Sequences.**

```text
Start (browser):  web → POST /calls (or /demo/calls) → platform creates `calls` row (state ringing), mints callerToken,
                  asks LineManager.prepare(call_id, mode, language, region, scenario) → 201 StartCallOut
                  web → POST /calls/{id}/webrtc/offer → voice runtime answers (SmallWebRTCConnection), starts the
                  pipeline → CallSink.call_opened → line.opened
Each turn:        caller speech → (VAD → STT | browser text) → redact → NLU → engine → tools → CallSink.turn/slot/stage
                  → reply (TTS audio or line.say) → CallSink.turn (line) → CallSink.latency
Hand-off:         engine event → CallSink.handoff_requested → HandoffTicket → line says "Connecting you with a person"
                  → handoff.requested on the switchboard → a person accepts (POST …/handoff/accept) → platform calls
                  LineControl.take_over → person types (POST …/say) or speaks on a WebRTC leg
At hang-up:       CallSink.call_closed(closing) → platform, in order: purge unretained turns; create the claim (when a
                  loss was reported); build TriageInput from the claim file + policy + call facts; TriageScorer.score;
                  persist routing_decisions; open siu_referrals when `siu_referral`; CallScorer.score; persist
                  qa_scores; publish line.closed, claim.created, qa.flagged when queued.
```

The platform runs the scorers inline (they take milliseconds) inside the closing task, never on the request path.

---

# Part 4: Voice signalling and the data-channel protocol

Code: `backend/claimvoice/schemas/voice.py` (msgspec tagged unions, decoders `client_decoder` / `server_decoder`).
Verified offline by `scripts/smoke/voice_smoke.py` (docs/adr/0001, docs/adr/0002).

## 4.1 Modes

| Mode | Caller → line | Line → caller | Offline? |
|---|---|---|---|
| `browser_speech` (default) | browser `SpeechRecognition` → `caller.text` on the data channel; microphone track also sent for the recording and server VAD (barge-in) | `line.say` → browser `speechSynthesis` (local system voices, `en-CA` / `fr-CA`) | Yes, no keys. Chrome recognition is on-device when the language pack is installed (`SpeechRecognition.available({ langs, processLocally: true })` returns `available`), otherwise it uses the browser's own cloud service |
| `voice` | microphone track → Silero VAD → cloud STT | cloud TTS audio on the return track; `line.say` as captions | Needs `STT_PROVIDER` / `TTS_PROVIDER` keys; with fakes it runs for tests and latency only |
| `typed` | `caller.text` from a text box | `line.say` shown as text (and spoken when the caller turns sound on) | Yes. Accessibility "read instead" and no-microphone fallback |

The web app picks `browser_speech` when recognition is available, else `typed`, and lets the caller switch to typing
at any point (`client.hello` again with the new mode).

## 4.2 WebRTC (SmallWebRTC, no media server)

1. `POST /calls` → `ConnectInfo { callerToken, offerUrl, iceUrl, iceServers, dataChannelLabel: "claimvoice" }`.
2. Browser creates `RTCPeerConnection({ iceServers })`, adds the microphone track (`audio: { echoCancellation:
   true, noiseSuppression: true, autoGainControl: true }`; omitted in `typed` mode), creates the data channel
   `"claimvoice"` (ordered), creates the offer.
3. `POST {offerUrl}` with `Authorization: Bearer <callerToken>` and `SdpOffer { sdp, type: "offer", pcId?,
   restartPc? }` → `SdpAnswer { sdp, type: "answer", pcId }`.
4. Trickle ICE: `PATCH {iceUrl}` with `IcePatch { pcId, candidates: [{ candidate, sdpMid, sdpMLineIndex }] }`
   (batch candidates every 100 ms) → `204`. Host candidates suffice on one machine; `VOICE_ICE_SERVERS` adds
   STUN/TURN for remote callers.
5. When the channel opens the browser sends `client.hello`, then the text **`ping-<ms>` about every second**
   (Pipecat keep-alive; a gap over 3 s marks the caller as disconnected and queues outgoing messages).
6. Renegotiation (e.g. turning the microphone on after starting typed): a new offer with the same `pcId`.
7. Ending: `caller.hangup` on the channel (or `POST /calls/{id}/hangup` with the caller token), then close the peer
   connection. The server ends the call itself after `maxSeconds`, two silent re-prompts, or a lost connection for
   30 s.

Audio formats: the server pipeline runs at 16 kHz mono in, 24 kHz mono out (resampled by Pipecat); Opus on the wire.

## 4.3 Data-channel messages (JSON text frames, `type`-tagged)

Client → server:

| `type` | Fields | Meaning |
|---|---|---|
| `client.hello` | `mode`, `language` (`en`/`fr`/`auto`), `recognition` (`on_device`/`cloud`/`none`), `voices[]` | sent on open and on mode switch |
| `caller.text` | `text`, `final`, `language`, `confidence?`, `startedAtMs?`, `endedAtMs?` | recognised or typed caller words; only `final: true` drives the dialogue; interim text feeds captions |
| `caller.barge_in` | `atMs` | the browser heard the caller start speaking while it was speaking a line turn |
| `line.spoken` | `turnId`, `event` (`start`/`end`/`cancelled`), `atMs` | browser speech progress (turn timing, barge-in bookkeeping) |
| `caller.hangup` | – | caller ended the call |

Server → client:

| `type` | Fields | Client does |
|---|---|---|
| `call.ready` | `callId`, `mode`, `language`, `stage` | show the call screen |
| `line.say` | `turnId`, `text`, `language`, `voiceLang` (`en-CA`/`fr-CA`), `interruptible`, `expectsAnswer` | speak it (browser_speech) and caption it |
| `line.stop` | `turnId`, `reason` (`barge_in`/`takeover`/`hangup`) | `speechSynthesis.cancel()` now |
| `transcript.turn` | `turn: Turn` | append to the caller's transcript |
| `transcript.partial` | `speaker: "caller"`, `text` | live caption |
| `claim_file.slot` | `slot: Slot`, `progress` | caller-side "what we have so far" (optional) |
| `call.stage` | `stage: StageInfo` | progress indicator |
| `call.flag` | `flag: Flag` | only `urgent_safety`, `card_number_removed`, `language_switched` are ever sent to the caller |
| `call.notice` | `kind`, `text` | accessible caption, e.g. `recording_paused` "Recording paused while we skip that number" |
| `call.handoff` | `handoff: HandoffInfo` | "Connecting you with a person…" with position |
| `call.ended` | `reason`, `claimNumber?`, `summary?`, `nextSteps[]`, `route?` `{ route, label, reasons: [{ text, atSeconds }] }` | end screen with the claim number and the route reveal (who looks first; never a decision) |
| `turn.metrics` | `turnId`, `sttMs`, `understandMs`, `toolsMs`, `planMs`, `firstAudioMs`, `totalMs` | ignore in the UI (eval and latency report only) |

`call.notice.kind`: `recording_on`, `recording_off`, `recording_paused`, `recording_resumed`, `card_number_removed`,
`photo_link_sent`, `waiting_for_person`, `person_joined`, `back_with_line`, `language_switched`, `connection_weak`.

**Barge-in.** In `voice` mode the server VAD detects caller speech while the line is speaking, cancels TTS output
(Pipecat interruption) and sends `line.stop { reason: "barge_in" }`. In `browser_speech` mode the browser sends
`caller.barge_in` as soon as recognition reports speech during `speechSynthesis`, cancels speaking locally, and the
server marks that line turn `interrupted`. Either way the engine treats the caller's next final text as the answer
to the interrupted question (or a correction of it).

## 4.4 WebSocket fallback

`GET ws(s)://<api>/api/v1/calls/{id}/ws?token=<callerToken>` when WebRTC cannot connect within 8 s (or the browser
has no `RTCPeerConnection`). Text frames carry exactly the Part 4.3 JSON messages (no `ping-` keep-alive; the
WebSocket's own ping applies). Binary frames, client → server, are 16-bit little-endian PCM, 16 kHz mono, 20 ms
(640 bytes); server → client binary frames are 24 kHz mono PCM16 line audio in `voice` mode. Close codes: `4401`
bad token, `4404` unknown or ended call, `4409` another connection already holds the caller leg, `1000` normal end.

## 4.5 Supervisor audio legs

`POST /calls/{id}/listen` and `…/handoff/accept` return `ListenOut`. For calls with server audio (`voice` mode, or
`browser_speech` with the microphone track), `mode: "audio"` and a receive-only `ConnectInfo` (same offer/ICE flow,
`Authorization: Bearer <listenerToken>`): the listener hears the caller and the line mixed. Without server audio,
`mode: "transcript"`: the per-call SSE stream is the live view (the dock's mini player then draws its waveform from
the stream's turn timing). Take over turns the person's microphone on: `TakeoverOut.connect` is a send-receive leg and
a third (person) voice joins the waveform while ClaimVoice keeps taking notes. Without a microphone, the person types
(`POST /calls/{id}/say`), spoken in the line's voice as "Renée from Larkspur".

---

# Part 5: The dialogue state machine

Code: `backend/claimvoice/dialogue/stages.py` (unit-tested). Control flow is explicit; language understanding fills
values **inside** a stage and never chooses the next stage.

## 5.1 Stages and the seven-step script track

Ten scripted stages, shown to people as **seven steps** (the script track on a line, "Step 4 of 7 · What happened" on
the line desk): `DISPLAY_STEPS` and `STAGE_STEP` in `stages.py`. Safety is asked as soon as the caller is identified
("Before anything else: is everyone safe?"), and urgent safety is also watched on every turn (§5.2).

| Step | `Stage` | Label (EN / FR) | Done when (→ event) |
|---|---|---|---|
| 1 Consent | `greeting` | Greeting / Accueil | greeting spoken (`greeted`) |
| 1 Consent | `consent` | Recording consent / Consentement à l'enregistrement | yes → `consent_given`; no → `consent_refused` (recording stops, notes only, a person offered). One-party regions announce and continue (`not_required` recorded). In all-party regions nothing is kept before the yes |
| 2 Policy | `identity` | Caller and policy / Appelant et police | policy found (`PolicyDirectory.find_policy`) and one identity detail matches (DOB or postal code) → `identity_verified`; after 3 failed attempts → `identity_failed` |
| 3 Safety | `safety` | Safety check / Vérification de sécurité | "Is everyone safe, and is anything dangerous right now?" answered no → `safety_clear` |
| 4 What happened | `loss_type` | What happened / Ce qui s'est passé | loss type known → `loss_type_set` |
| 4 What happened | `loss_details` | Details / Détails | every required question of the loss type's script answered (plus surge questions when switched on) → `details_complete` |
| 5 Photos | `photos` | Photos / Photos | link texted (`photos_sent`) or declined (`photos_declined`) |
| 6 Coverage | `coverage` | Coverage basics / Couverture | coverage summary read in plain words, never a decision → `coverage_explained` |
| 7 Read-back | `read_back` | Read-back / Relecture | caller confirms the summary → `read_back_confirmed`; a correction (`read_back_corrected`) updates values and re-reads only what changed |
| 7 Read-back | `wrap_up` | Wrap-up / Conclusion | claim number and next steps given → `wrap_up_done` → `ended` |
| (kept) | `handoff` | With a person / Avec une personne | `handoff_completed` → `ended`; `handoff_returned` → the interrupted stage |
| (kept) | `ended` | Ended / Terminé | terminal |

## 5.2 Global events (valid in every active stage)

| Event | Goes to | Raised when |
|---|---|---|
| `urgent_safety` | `handoff` (priority urgent) | the hand-off rules' urgent words: injury, fire or smoke, smell of gas, someone trapped, water near the electrical panel, a downed power line. The line first tells the caller, in their language, to get to safety and call 911, then stays on the line ("He is outside and still on the line"). Safety outranks consent: this works even before consent is answered |
| `handoff_requested` | `handoff` | caller asks for a person (any wording, EN/FR) `askedTimes` times (default once) |
| `low_confidence` | `handoff` | `lowConfidenceTurns` consecutive turns not understood after one re-ask |
| `distress_detected` | `handoff` | wording-based distress ≥ `distressThreshold` (never voice tone, accent or speech rate) |
| `tool_failed` | `handoff` | a required tool (policy lookup) failed or timed out twice |
| `supervisor_takeover` | `handoff` | a person took the call |
| `caller_hung_up`, `silence_timeout` | `ended` | caller left; two re-prompts unanswered |

In-stage events (no transition): `slot_corrected`, `card_number_detected` (digits redacted before storage, recording
paused for that segment, caller told "For your security, please don't share card numbers on this line"),
`language_switched` (EN↔FR, labels and voice follow), `off_script` (short answer or "I'll note that", then the
pending question), `repeat_requested`, `barge_in`, `whisper_received` (a typed note from a supervisor that ClaimVoice
acts on at its next turn, e.g. adds "Is the garage skylight damaged too?" to the current stage; never spoken as a
whisper and never heard by the caller).

Wait for a person: after `maxWaitSeconds` without acceptance the line offers a call-back (`callback_offered`) and,
if the caller agrees, finishes the claim file itself. Urgent-safety hand-offs never fall back to the line.

## 5.3 Language

`language: "auto"` starts in the region's first language (French first in `CA-QC`, as required by Quebec's Charter
of the French language) with a bilingual greeting; the first caller turn decides. A caller can switch at any time.
Prompts, labels, read-back and the summary follow the caller's language; `summaryEn` is produced for adjusters.

## 5.4 Claim-file fields (slot keys)

Labels are the claim-file labels (EN). The script per loss type (`/settings/scripts`) decides which are asked and
required; `section` places them in `ClaimFile.sections`. Code: `backend/claimvoice/dialogue/slots.py` (`SLOT_CATALOG`
with each key's section, kind and EN/FR label, and `display()` for how a value reads).

| Section | Keys |
|---|---|
| caller | `caller_name`, `caller_relationship` (policyholder, spouse, driver, other), `callback_number`, `preferred_language` |
| policy | `policy_number`, `identity_check` (passed / failed; never the DOB itself), `insured_item` |
| loss | `loss_type`, `loss_date`, `loss_time`, `loss_place`, `loss_description`, `caller_damage_estimate_band` |
| details (auto) | `vehicle_drivable`, `damage_areas`, `other_party_involved`, `other_party_name`, `other_party_insurer`, `other_party_plate`, `police_report_filed`, `police_report_number`, `witnesses`, `airbags_deployed` |
| details (property) | `water_source`, `water_still_entering`, `rooms_affected`, `mitigation_taken`, `roof_or_window_damage`, `siding_or_fence_damage`, `open_to_weather`, `debris_source`, `home_livable`, `temporary_lodging_needed`, `fire_out`, `fire_department_attended`, `items_stolen`, `forced_entry` |
| details (any) | `extra_notes` (answers to a supervisor's whispered question, and off-script questions for the adjuster) |
| safety | `injury_reported`, `injury_detail`, `danger_now`, `emergency_services_called`, `power_out` (a surge question) |
| photos | `photos_promised`, `photo_link_sent_to` (masked) |
| coverage | `coverage_lines_mentioned`, `deductible_mentioned` |
| next_steps | `next_steps_given`, `adjuster_contact_window` |

## 5.5 Prompts and scripts

Scripts live in the database (`scripts`, versioned, edited in Settings) and are seeded from
`backend/claimvoice/dialogue/scripts/*.yml` (one file per loss type, bilingual). The engine never improvises a
question: every prompt the line speaks comes from the script, the stage's fixed lines, or a template filled with slot
displays. Language understanding (fake or cloud) only returns intents, slot values and safety/distress signals.

## 5.6 Scripted test callers

`eval/callers/*.yml` drive the dialogue eval and the seeded live demo lines:

```yaml
key: calgary-windstorm       # also a StartCallIn.scenario
title: Chinook wind damage to a home, Calgary
language: en                 # en | fr
region: CA-AB
caller_phone: "+14035550142"
policy_number: LM-AB-204118
turns:                       # caller lines in order; each is sent after the line's turn ends
  - text: "Hi, the wind last night tore up my house."
  - text: "…"
    barge_in_after_ms: 600   # optional: start this line while the line is still speaking
expect:                      # what the eval checks at the end
  final_stage: ended
  handoff: false
  flags: [surge]
  route: adjuster
  slots: { loss_type: wind, loss_time: "02:30", roof_or_window_damage: true, home_livable: true }
```

---

# Part 6: Routing checks (the severity and fraud-indicator models)

Code: `backend/claimvoice/ml/` (feature contract in `ml/features.py`). Decision record: docs/adr/0004. People see them as
the **size check** (`size`, severity/complexity) and the **closer-look check** (`closer_look`, fraud indicators).

## 6.1 Routes and rules

The models produce calibrated probabilities; routing combines them with fixed rules, which always win:

| Rule (applied in order) | Result |
|---|---|
| Urgent safety on the call | `adjuster`, priority, whatever the scores |
| Injury reported | never `fast_track` |
| Closer-look probability ≥ threshold **and** at least 2 signs present | `special_investigation` and a closer-look referral opens (a request for review, never a denial). A person may change the route; the referral stays open for the special investigator |
| Size probability ≥ adjuster threshold, water still entering, or the building is open to the weather (roof hole, smashed skylight) | `adjuster` |
| Otherwise | `fast_track` |

Thresholds are set on validation data for fixed targets (size: the highest threshold that still sends ≥ 90 % of large
or complex claims to an adjuster; closer look: the best F1 among thresholds that refer ≤ 8 % of claims with at least
two signs) and stored with the model version (`ml/artifacts/models.json`). The closer-look check reports the signs
present out of the fourteen it checks (`ml/features.py` `SIGNS`); a referral needs at least two.

## 6.2 Features

`SEVERITY_FEATURES` and `FRAUD_FEATURES` in `ml/features.py` are the complete input lists. Never features:
region, language, age band (fairness testing only), postal code, date of birth, names, and any voice-derived signal
(stress, accent, pitch, speech rate). `TriageInput.fairness_groups` carries region, language and age band for the
fairness report only.

`build_features(claim_file, policy, call)` builds `TriageInput.features` from the current claim-file values, the
policy facts (`line`, `region`, `status`, `effective_from`, `effective_to`, `coverage_changed_at`, `deductible`,
`coverage_limit`, `prior_claims_36m`, `vehicle_age_years`) and the call (`answered_at`, `surge_match`,
`key_fact_corrections`, `photos_declined`, and `facts` = `CallClosing.facts`). Training uses the same function, so
there is no training/serving skew. Extra keys the scorer reads but the models never see: `urgent_safety` (a rule) and
`currency`/`region` (only to label the settlement range).

## 6.3 Gates (CI, `make eval`)

| Gate | Limit |
|---|---|
| XGBoost PR-AUC vs logistic baseline (both models) | ≥ baseline + 0.02 |
| Expected calibration error after isotonic calibration | ≤ 0.05 |
| Fairness: closer-look rate by region / language / age band within the band around the overall rate | ±1.5 points |
| Fairness: fast-track rate by region / language / age band within the band around the overall rate | ±5 points |
| SHAP top-5 stability across 5 bootstrap refits (Jaccard) | ≥ 0.70 |
| Score PSI, recent synthetic weeks vs reference | ≤ 0.25 (Watch at 0.10; Act at 0.25 pauses fast-track) |

A candidate version goes into use only when every gate passes **and** two different people have signed it off: one
for claims (a supervisor) and one for model risk (compliance).

---

# Part 7: Module map

Cross-module changes go through Part 3 and `backend/claimvoice/contracts.py`, updated in the same commit as the
code that needs them, together with this document.

| Area | Responsibility | Paths |
|---|---|---|
| **Platform and API** | Litestar app and every HTTP route and SSE stream; settings; auth, sessions, CSRF, rate limits; organisations, members, invitations, RBAC and tenant isolation; audit chain; domain tables and migrations (`0002+`); policies and policyholders; `SqlCallSink`, `PolicyDirectory`, `OrgPlaybook`; claims, routing persistence, SIU referrals, QA persistence and review queue, model registry API, settings, retention job, photo links and uploads; the seed (Larkspur Mutual, history, live lines, surge); the demo clock | `backend/claimvoice/{platform,api,schemas,seed}/**`, new `backend/claimvoice/{calls,claims,policies,settings}/**`, `backend/claimvoice/{clock,config,cli}.py`, `backend/alembic/**` |
| **Voice, dialogue and models** | Pipecat pipelines over SmallWebRTC and the WebSocket fallback, `LineManager` (`LineControl`), speech adapters and fakes; the dialogue engine, scripts (EN/FR), slot parsing, corrections, barge-in, hand-off logic; NLU fake and the LiteLLM adapter; mid-call tools and budgets; PCI redaction; recordings; synthetic intake data, severity and fraud models (baselines, XGBoost, Optuna, calibration, SHAP reasons, fairness, cards, MLflow, drift); `TriageScorer`; the call-quality scorer (`CallScorer`); eval suites (dialogue, latency, models, qa) | `backend/claimvoice/{voice,dialogue,nlu,tools,ml,qa}/**`, `eval/**`, `scripts/**` |
| **Web app** | Nuxt 3 + TypeScript + Tailwind 4.1, built to `frontend/DESIGN.md` ("On the line"): the floating dock as the only navigation (Lines · Claims · Quality · Routing checks · Settings, plus the line you are on), the landing page with the recorded call and "Ring the demo line" (`/call`: WebRTC, Web Speech, captions, typed call), sign-in and demo sign-in, the line desk (SSE), the live call view, claim files (transcript-span links, wavesurfer.js recording band, photos, route reveal, closer-look signs), quality review, routing checks and fact sheets, settings, activity (audit), the photo-link page `/p/{token}` | `frontend/**` |
| **Shared contracts** | Wire schemas, in-process interfaces, stages and events, roles, rubric | `backend/claimvoice/schemas/**`, `backend/claimvoice/contracts.py`, `backend/claimvoice/dialogue/stages.py`, `backend/claimvoice/platform/permissions.py`, `backend/claimvoice/qa/rubric.py` |
| **Tests** | Backend tests by area under `backend/tests/{platform,api,calls,claims,voice,dialogue,ml,qa,seed}/`; web tests in `frontend/tests/` | |
| **Project** | Docs, decision records, Makefile, CI | `docs/**`, `Makefile`, `.github/**`, `README.md`, `.env.example` |

---

# Part 8: Project conventions

- Python 3.13, `backend/.venv`; tools as `.venv/bin/python -m pytest|ruff|mypy|alembic|uvicorn`. Ruff (line 120)
  and mypy clean. Tests: `asyncio_mode=auto`; no test needs a server, a network or a key.
- Business time only through `claimvoice.clock`; security timers through `clock.real_now()`; in-call timing through
  `time.perf_counter()`.
- Every fake is deterministic. Cloud adapters are optional extras and are only constructed when their key is set.
- **Words the product never shows** (UI text, labels, API `*Label` fields, fact sheets, summaries): RAG, retrieval,
  embeddings, vector, LLM, model or provider names (GPT, Gemini, Groq, Llama, Whisper, Deepgram, Cartesia,
  Pipecat), LiteLLM, prompt, tokens, SQL, pipeline, latency, fallback, cache, SHAP, slots, model scores, confidence
  decimals. Say "the line", "ClaimVoice", "routing checks", "what we heard", "why this route", "signs worth a closer
  look", "likely size", "fact sheet", "quality review". Rates as frequencies ("96 in 100", "about 7 in 10").
  Compliance wording is "designed to support" / "aligned with", never "certified" or "compliant".
- Plain words for people: no codes in labels, dates in the viewer's language ("Thursday 8 January, 9:40"), money with
  currency, reasons as sentences ("Reported 9 days after the loss"), never "positive class" or "p=0.83".
- Status is never shown by colour alone (labels and icons travel with every band, flag and route).
- Personal data: phone, email and postal code masked in every response; DOB never returned; card numbers never
  stored anywhere.
