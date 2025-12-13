// Wire types for the ClaimVoice API (docs/API_CONTRACT.md Part 1 and Part 4). Mirrors backend/claimvoice/schemas/*.py
// (msgspec, camelCase). Timestamps are ISO-8601 strings; the app formats them through utils/format.ts in demo time.

export type Lang = 'en' | 'fr'
export type Iso = string
export type IsoDate = string

export interface Page<T> { items: T[], page: number, pageSize: number, total: number, totalPages: number }
export interface Labeled { key: string, label: string }
export interface PersonRef { id: string, name: string }
export interface FieldError { field: string, message: string }
export interface Problem {
  type: string
  title: string
  status: number
  code: string
  detail?: string | null
  errors?: FieldError[] | null
  requestId?: string | null
}
export interface TextSpan { turnId: string, start: number, end: number }
export interface Money { amount: number, currency: 'CAD' | 'USD' }
export interface ClockInfo { today: IsoDate, now: Iso, demo: boolean, timezone: string }

// ---------------------------------------------------------------- auth, org
export type Role = 'admin' | 'supervisor' | 'intake_agent' | 'adjuster' | 'siu_investigator' | 'compliance'
export interface User { id: string, email: string, fullName: string, preferredLanguage: Lang, avatarColor: string, createdAt: Iso }
export interface OrgSummary { id: string, name: string, slug: string, role: Role, roleLabel: string, isSample: boolean }
export interface Org { id: string, name: string, slug: string, timezone: string, regions: string[], languages: Lang[], isSample: boolean, createdAt: Iso }
export interface MembershipInfo { role: Role, roleLabel: string, title: string | null, permissions: string[] }
export interface Me {
  user: User
  activeOrg: Org | null
  membership: MembershipInfo | null
  orgs: OrgSummary[]
  session: { expiresAt: Iso, absoluteExpiresAt: Iso }
  clock: ClockInfo
}
export interface SessionState { me: Me | null, clock: ClockInfo }
export interface Member {
  membershipId: string
  userId: string
  fullName: string
  email: string
  role: Role
  roleLabel: string
  title: string | null
  avatarColor: string
  joinedAt: Iso
  lastActiveAt: Iso | null
  isYou: boolean
}
export interface Invitation {
  id: string
  email: string
  role: Role
  roleLabel: string
  invitedBy: string | null
  createdAt: Iso
  expiresAt: Iso
  status: 'pending' | 'accepted' | 'revoked' | 'expired'
  acceptUrl?: string | null
}
export interface RoleInfo { role: Role, label: string, description: string, permissions: string[] }

export interface Meta {
  product: string
  version: string
  languages: Labeled[]
  lossTypes: { key: string, label: string, line: string }[]
  regions: { code: string, label: string, country: string, consentRule: string }[]
  stages: Labeled[]
  routes: Labeled[]
  roles: Labeled[]
  demoScenarios: Labeled[]
}

// ---------------------------------------------------------------- calls
export type CallMode = 'voice' | 'browser_speech' | 'typed'
export type LineState = 'ringing' | 'with_line' | 'waiting_for_person' | 'with_person' | 'wrapping_up' | 'ended'
export type Speaker = 'caller' | 'line' | 'person' | 'system' | 'whisper'
export type FlagKind =
  | 'urgent_safety' | 'distress' | 'card_number_removed' | 'low_confidence' | 'siu_signal'
  | 'consent_refused' | 'surge' | 'language_switched'

export interface Flag { kind: FlagKind, label: string, detail: string, severity: 'info' | 'warning' | 'critical', at: Iso, turnId?: string | null }
export interface StageInfo { key: string, label: string, step: number, stepLabel: string, steps: number, nextLabel: string | null }
export interface Listener { userId: string, name: string, mode: 'listening' | 'took_over' }
export type HandoffReason =
  | 'caller_asked' | 'urgent_safety' | 'distress' | 'low_confidence' | 'identity_unverified' | 'tool_failed'
  | 'consent_refused' | 'supervisor'
export interface HandoffInfo {
  id: string
  callId: string
  reason: HandoffReason
  reasonLabel: string
  detail: string
  priority: 'urgent' | 'high' | 'normal'
  state: 'waiting' | 'accepted' | 'completed' | 'returned_to_line' | 'callback_offered'
  requestedAt: Iso
  waitingSeconds: number
  acceptedBy: PersonRef | null
  acceptedAt: Iso | null
  callerLabel: string
  lineLabel: string
  place: string | null
  lossTypeLabel: string | null
  language: Lang
  summary: string
  actionsTaken: string[]
  to: PersonRef | null
  team: 'intake' | 'adjusters' | 'siu' | null
}
export interface Mood { key: 'calm' | 'unsettled' | 'shaken' | 'upset', label: string, detail: string | null }
export interface HeardPillInfo { key: string, text: string, tone: 'normal' | 'caution' }
export interface LiveLine {
  callId: string
  lineLabel: string
  state: LineState
  stateLabel: string
  stage: StageInfo
  mode: CallMode
  language: Lang
  callerLabel: string
  callerVerified: boolean
  callerPhoneMasked: string | null
  region: string | null
  regionLabel: string | null
  lossType: string | null
  lossTypeLabel: string | null
  answeredAt: Iso
  flags: Flag[]
  mood: Mood
  handoff: HandoffInfo | null
  listeners: Listener[]
  inSurge: boolean
  lastAsked: { text: string, textEn: string | null } | null
  place: string | null
  heard: HeardPillInfo[]
  claimFileProgress: number
  isSample: boolean
}
export interface CallSummary {
  id: string
  reference: string
  startedAt: Iso
  endedAt: Iso | null
  durationSeconds: number | null
  state: LineState
  stateLabel: string
  mode: CallMode
  language: Lang
  callerLabel: string
  regionLabel: string | null
  lossTypeLabel: string | null
  outcome: 'claim_created' | 'handed_off' | 'abandoned' | 'no_claim' | 'in_progress'
  outcomeLabel: string
  claimId: string | null
  claimNumber: string | null
  flags: Flag[]
  qaScore: number | null
  isSample: boolean
}
export interface Consent {
  rule: 'one_party' | 'all_party'
  ruleLabel: string
  region: string
  answer: 'given' | 'refused' | 'not_required' | 'pending'
  answerLabel: string
  recording: boolean
  askedAt: Iso | null
  turnId: string | null
}
export interface CallDetail extends CallSummary {
  stage: StageInfo
  stages: StageInfo[]
  consent: Consent
  policyId: string | null
  policyNumber: string | null
  holderId: string | null
  handoff: HandoffInfo | null
  listeners: Listener[]
  summary: string | null
  summaryEn: string | null
  recordingAvailable: boolean
  surgeId: string | null
  lineLabel?: string | null
  place?: string | null
}
export interface Turn {
  id: string
  seq: number
  speaker: Speaker
  speakerLabel: string
  text: string
  textEn?: string | null
  language: Lang
  atMs: number
  endMs: number
  stage: string
  confidence: number | null
  interrupted: boolean
  redactions: number
  flags: FlagKind[]
}
export interface Transcript { callId: string, language: Lang, retained: boolean, notice: string | null, turns: Turn[] }
export type SlotSource = 'heard' | 'policy_record' | 'tool' | 'person'
export interface SlotHistory { value: unknown, display: string, source: SlotSource, changedBy: string | null, at: Iso, span: TextSpan | null, note: string | null }
export interface Slot {
  key: string
  label: string
  value: unknown
  display: string
  confidence: number | null
  confidenceLabel: 'sure' | 'likely' | 'check' | null
  source: SlotSource
  sourceLabel: string
  span: TextSpan | null
  heardAtSeconds: number | null
  changedAtSeconds: number | null
  confirmed: boolean
  required: boolean
  history: SlotHistory[]
}
export type SectionKey = 'caller' | 'policy' | 'loss' | 'details' | 'safety' | 'photos' | 'coverage' | 'next_steps'
export interface ClaimFileSection { key: SectionKey, label: string, slots: Slot[] }
export interface ClaimFile {
  callId: string
  claimId: string | null
  lossType: string | null
  lossTypeLabel: string | null
  progress: number
  missing: string[]
  sections: ClaimFileSection[]
}
export interface CallEvent { id: string, at: Iso, atMs: number, kind: string, label: string, actor: string | null, data: Record<string, unknown> }
export interface StartCallIn {
  mode?: CallMode
  language?: Lang | 'auto'
  callerPhone?: string | null
  region?: string | null
  scenario?: string | null
}
export interface IceServerInfo { urls: string[], username?: string | null, credential?: string | null }
export interface ConnectInfo {
  callId: string
  callerToken: string
  offerUrl: string
  iceUrl: string
  websocketUrl: string
  dataChannelLabel: string
  iceServers: IceServerInfo[]
  maxSeconds: number
}
export interface StartCallOut { call: CallDetail, connect: ConnectInfo }
export interface ListenOut { mode: 'audio' | 'transcript', connect: ConnectInfo | null }
export interface TakeoverOut { call: CallDetail, connect: ConnectInfo | null }
export interface WhisperOut { id: string, at: Iso }
export interface SmsMessage { id: string, toMasked: string, body: string, sentAt: Iso, status: 'queued' | 'sent' | 'failed' }

// ---------------------------------------------------------------- claims
export type Route = 'fast_track' | 'adjuster' | 'special_investigation'
export type ClaimStatus = 'new' | 'assigned' | 'in_review' | 'waiting_on_customer' | 'closed'
export interface RouteSummary { route: Route, label: string, decidedBy: 'model' | 'person', topReason: string }
export interface ClaimSummary {
  id: string
  claimNumber: string
  status: ClaimStatus
  statusLabel: string
  line: 'auto' | 'property'
  lossType: string
  lossTypeLabel: string
  lossDate: IsoDate | null
  lossPlace: string | null
  holderName: string
  policyNumber: string
  regionLabel: string
  language: Lang
  reportedAt: Iso
  route: RouteSummary | null
  urgentSafety: boolean
  siuOpen: boolean
  photos: number
  assignedTo: PersonRef | null
  surgeLabel: string | null
  isSample: boolean
}
export interface SummaryLink { start: number, end: number, turnId: string, atSeconds: number | null }
export interface InShort { text: string, links: SummaryLink[], checkedBy: PersonRef | null, checkedAt: Iso | null }
export interface Claim extends ClaimSummary {
  callId: string | null
  policyId: string
  holderId: string
  description: string
  descriptionEn: string | null
  inShort: InShort
  flags: Flag[]
  file: ClaimFile
  nextSteps: string[]
  recordingAvailable: boolean
}
export type MomentKind = 'consent' | 'policy' | 'safety' | 'sign' | 'photos' | 'read_back' | 'claim_number' | 'handoff' | 'whisper'
export interface Moment { kind: MomentKind, label: string, atSeconds: number, turnId: string | null }
export interface RecordingSegment { turnId: string, speaker: 'caller' | 'line' | 'person' | 'system', startSeconds: number, endSeconds: number, paused: boolean }
export interface Recording {
  available: boolean
  reason: string | null
  audioUrl: string | null
  durationSeconds: number | null
  peaks: number[] | null
  segments: RecordingSegment[]
  moments: Moment[]
  hushes: [number, number][]
  retainedUntil: IsoDate | null
}
export interface Photo {
  id: string
  url: string
  thumbnailUrl: string
  caption: string | null
  receivedAt: Iso
  source: 'text_link' | 'uploaded_by_staff'
  width: number
  height: number
}
export interface Reason { feature: string, text: string, direction: 'raises' | 'lowers', weight: number, turnId: string | null, atSeconds: number | null }
export interface ScoreBand {
  probability: number
  band: string
  label: string
  detail: string | null
  settleRange: { low: number, high: number, currency: 'CAD' | 'USD' } | null
}
export interface SiuIndicator {
  key: string
  label: string
  evidence: string
  source: 'call' | 'policy' | 'claim_history' | 'weather'
  sourceLabel: string
  turnId: string | null
  atSeconds: number | null
  weight: number
}
export interface RoutingDecision {
  claimId: string
  route: Route
  routeLabel: string
  modelRoute: Route
  decidedAt: Iso
  severity: ScoreBand
  fraud: ScoreBand | null
  reasons: Reason[]
  signs: SiuIndicator[] | null
  signsChecked: number
  acceptedBy: PersonRef | null
  acceptedAt: Iso | null
  rulesApplied: string[]
  modelVersions: Record<string, string>
  override: { route: Route, reason: string, by: PersonRef, at: Iso } | null
  statement: string
}
export interface SiuReferral {
  id: string
  claimId: string
  claimNumber: string
  status: 'open' | 'investigating' | 'closed_no_concern' | 'returned_to_adjuster'
  statusLabel: string
  openedAt: Iso
  score: number
  indicators: SiuIndicator[]
  decidedBy: PersonRef | null
  decidedAt: Iso | null
  note: string | null
  statement: string
}

// ---------------------------------------------------------------- switchboard
export interface Surge {
  id: string
  kind: 'hail' | 'flood' | 'wind' | 'winter_storm' | 'rainfall' | 'wildfire'
  kindLabel: string
  title: string
  region: string
  regionLabel: string
  areaLabel: string
  startedAt: Iso
  endedAt: Iso | null
  active: boolean
  headline: string
  source: string
  callsLastHour: number
  usualCallsPerHour: number
  multiplier: number
  sinceLabel: string
  surgeQuestionsOn: boolean
  waitForPersonSeconds: number
  standbyAvailable: number
  standbyCalled: boolean
  policiesInArea: number
  claimsSoFar: number
  guidance: string
}
export interface TodayStats {
  callsAnswered: number
  answeredFirstRingShare: number
  medianHandleSeconds: number
  handoffs: number
  claimsCreated: number
  averageQaScore: number | null
  surgeCalls: number
}
export interface SwitchboardSnapshot {
  lines: LiveLine[]
  handoffTray: HandoffInfo[]
  surge: Surge | null
  recentClaims: ClaimSummary[]
  freePeople: PersonRef[]
  caption: string
  today: TodayStats
  lastEventId: number
}
export interface Envelope<T = unknown> { type: string, at: Iso, orgId: string, callId: string | null, data: T }
export interface LineClosed { callId: string, outcome: string, outcomeLabel: string, claimId: string | null, claimNumber: string | null }

// ---------------------------------------------------------------- quality
export type Band = 'good' | 'needs_attention' | 'failed'
export interface Bead { key: string, label: string, passed: boolean | null, detail: string | null }
export interface QaItem {
  key: string
  label: string
  passed: boolean | null
  points: number
  maxPoints: number
  critical: boolean
  method: 'rule' | 'language_check'
  note: string
  evidence: { turnId: string, quote: string }[]
  atSeconds: number | null
  reviewerVerdict: 'agree' | 'disagree' | null
  reviewerNote: string | null
}
export interface QaScore {
  callId: string
  claimId?: string | null
  claimNumber: string | null
  score: number
  band: Band
  bandLabel: string
  status: 'needs_review' | 'reviewed' | 'auto_passed'
  items: QaItem[]
  beads: Bead[]
  focus: { atSeconds: number, text: string } | null
  scoredAt: Iso
  scorerVersion: string
  reviewedBy: PersonRef | null
  reviewedAt: Iso | null
  reviewNote: string | null
}
export interface QaQueueItem {
  callId: string
  claimId?: string | null
  reference: string
  claimNumber: string | null
  startedAt: Iso
  durationSeconds: number
  language: Lang
  lossTypeLabel: string | null
  score: number
  band: Band
  bandLabel: string
  failedItems: string[]
  beads: Bead[]
  callerLabel: string
  lineLabel: string | null
  reviewer: PersonRef | null
  status: 'needs_review' | 'reviewed' | 'auto_passed'
  reasonQueued: string
}
export interface Agreement {
  reviewedCalls: number
  overall: number
  cohenKappa: number | null
  byItem: { key: string, label: string, reviewed: number, agreement: number }[]
}
export interface ReviewIn {
  items: { key: string, verdict: 'agree' | 'disagree', note?: string | null }[]
  note?: string | null
  coachingNote?: string | null
}

// ---------------------------------------------------------------- routing checks
export type CheckKey = 'size' | 'closer_look'
export interface MetricSet { auc: number, prAuc: number, brier: number, ece: number, recallAtThreshold?: number | null, precisionAtThreshold?: number | null, threshold?: number | null }
export interface GateResult { key: string, label: string, passed: boolean, value: number, limit: number }
export interface SignOff { side: 'claims' | 'model_risk', sideLabel: string, by: PersonRef | null, at: Iso | null, note: string | null, state: 'signed' | 'waiting' }
export interface CheckVersion {
  version: number
  stage: 'in_use' | 'candidate' | 'retired'
  algorithm: string
  inUseSince: IsoDate | null
  trainedOn: string
  metrics: MetricSet
  gates: GateResult[]
  gatesPassed: boolean
  signOffs: SignOff[]
}
export interface Check {
  key: CheckKey
  name: string
  question: string
  decides: string
  inUse: CheckVersion
  candidate: CheckVersion | null
  status: 'healthy' | 'watch' | 'act'
  statusLabel: string
  signedBy: PersonRef | null
}
export interface Bar { label: string, value: number, ours: boolean }
export interface Dot { dimension: 'region' | 'language' | 'age_band', group: string, label: string, rate: number, count: number, withinBand: boolean }
export interface WeekColumn { label: string, psi: number, status: 'stable' | 'watch' | 'act' }
export interface CompareRow { key: 'right' | 'investigators_agreed' | 'fair' | 'reasons_same', label: string, inUse: string, candidate: string, better: boolean | null }
export interface Question {
  key: 'right' | 'fair' | 'like_learned' | 'replace'
  question: string
  answer: string
  foot: string
  bars?: Bar[] | null
  dots?: Dot[] | null
  overallRate?: number | null
  band?: number | null
  weeks?: WeekColumn[] | null
  compare?: CompareRow[] | null
  signOffs?: SignOff[] | null
}
export interface RoutingChecks { caption: string, checks: Check[], questions: Question[], never: string[] }
export interface FactSection { key: string, title: string, body: string[] }
export interface Technical {
  test: MetricSet
  baseline: MetricSet
  randomForest: MetricSet | null
  roc: { x: number, y: number }[]
  pr: { x: number, y: number }[]
  calibration: { predicted: number, observed: number, count: number }[]
  split: string
  features: string[]
}
export interface FactSheet { key: CheckKey, name: string, version: number, sections: FactSection[], technical: Technical, versions: CheckVersion[] }
export interface FairnessRow {
  dimension: 'region' | 'language' | 'age_band'
  group: string
  label: string
  count: number
  flaggedRate: number
  truePositiveRate: number | null
  falsePositiveRate: number | null
  gap: number
  withinBand: boolean
}
export interface Fairness { key: CheckKey, version: number, overallRate: number, band: number, passed: boolean, rows: FairnessRow[], note: string }

// ---------------------------------------------------------------- settings
export interface Bilingual { en: string, fr: string }
export interface ScriptQuestion {
  slotKey: string
  label: string
  kind: string
  prompt: Bilingual
  required: boolean
  when: string | null
  choices: string[]
  surgeOnly: boolean
}
export interface Script {
  lossType: string
  lossTypeLabel: string
  line: 'auto' | 'property'
  version: number
  questions: ScriptQuestion[]
  updatedAt: Iso
  updatedBy: PersonRef | null
}
export interface ConsentRule {
  region: string
  regionLabel: string
  rule: 'one_party' | 'all_party'
  ruleLabel: string
  announcement: Bilingual
  basis: string
  onRefusal: string
  isDefault: boolean
}
export interface HandoffRules {
  urgentKeywords: string[]
  askedTimes: number
  lowConfidenceTurns: number
  distressThreshold: number
  identityAttempts: number
  offerPersonOnConsentRefusal: boolean
  maxWaitSeconds: number
  urgentSafetyAlways: boolean
}
export interface VoiceSetting { voice: string, speed: number }
export interface Languages {
  enabled: Lang[]
  voices: Record<string, VoiceSetting>
  default: Lang
  detectAutomatically: boolean
  frenchFirstRegions: string[]
}
export interface Retention {
  recordingsYears: number
  transcriptsYears: number
  photosYears: number
  claimFilesYears: number
  cardNumberMoments: 'always_removed'
  refusedConsentTranscripts: 'not_kept'
  deletionRequestsWaiting: number
  lastPurgeAt: Iso | null
  nextPurgeOn: IsoDate | null
}
export interface Privacy { privacyOfficerName: string, privacyOfficerEmail: string, privacyNoticeUrl: string | null }

// ---------------------------------------------------------------- audit
export interface AuditEntry {
  id: string
  seq: number
  at: Iso
  actorLabel: string
  action: string
  actionLabel: string
  targetType: string | null
  targetId: string | null
  targetLabel: string | null
  summary: string
  details: Record<string, unknown>
}
export interface ChainStatus { ok: boolean, checked: number, firstBrokenSeq: number | null, reason: string | null, checkedAt: Iso }

// ---------------------------------------------------------------- photo links
export interface PhotoLinkInfo { orgName: string, claimReference: string, language: Lang, expiresAt: Iso, maxPhotos: number, uploaded: number }

// ---------------------------------------------------------------- data channel (Part 4.3)
export type ServerMessage =
  | { type: 'call.ready', callId: string, mode: CallMode, language: Lang, stage: StageInfo }
  | { type: 'line.say', turnId: string, text: string, language: Lang, voiceLang: string, interruptible: boolean, expectsAnswer: boolean }
  | { type: 'line.stop', turnId: string, reason: 'barge_in' | 'takeover' | 'hangup' }
  | { type: 'transcript.turn', turn: Turn }
  | { type: 'transcript.partial', speaker: 'caller', text: string }
  | { type: 'claim_file.slot', slot: Slot, progress: number }
  | { type: 'call.stage', stage: StageInfo }
  | { type: 'call.flag', flag: Flag }
  | { type: 'call.notice', kind: string, text: string }
  | { type: 'call.handoff', handoff: HandoffInfo }
  | { type: 'call.ended', reason: string, claimNumber: string | null, summary: string | null, nextSteps: string[], route?: EndRoute | null }
  | { type: 'turn.metrics', turnId: string }

export interface EndRoute { route: Route, label: string, reasons: { text: string, atSeconds?: number | null }[] }

export type ClientMessage =
  | { type: 'client.hello', mode: CallMode, language: Lang | 'auto', recognition: 'on_device' | 'cloud' | 'none', voices: string[] }
  | { type: 'caller.text', text: string, final: boolean, language: Lang, confidence?: number | null, startedAtMs?: number | null, endedAtMs?: number | null }
  | { type: 'caller.barge_in', atMs: number }
  | { type: 'line.spoken', turnId: string, event: 'start' | 'end' | 'cancelled', atMs: number }
  | { type: 'caller.hangup' }
