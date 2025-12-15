// The local mock layer's in-memory database. Used only when the API mock is switched on (NUXT_PUBLIC_API_MOCK=1),
// for working on the web app without the API. It mirrors the sample organisation in docs/DATA.md.
import type {
  AuditEntry, CallDetail, CallEvent, Check, Claim, ClaimFile, ConsentRule, FactSheet, Fairness, HandoffRules,
  Invitation, Languages, LiveLine, Member, Meta, Photo, PhotoLinkInfo, Privacy, QaQueueItem, QaScore, Recording,
  Retention, Role, RoleInfo, RoutingChecks, RoutingDecision, Script, SiuReferral, SmsMessage, SwitchboardSnapshot,
  Transcript,
} from '~/types/api'

export interface MockPerson { userId: string, membershipId: string, fullName: string, email: string, role: Role, roleLabel: string, title: string, avatarColor: string }

export interface MockDb {
  /** Demo "now" when the seed was built (Thursday 8 January 2026, 7:42 a.m. Calgary = 14:42 UTC). */
  now: Date
  orgId: string
  meta: Meta
  people: MockPerson[]
  /** The person `POST /auth/demo` signs in as, per role. */
  demoPeople: Record<Role, string> // role -> userId
  permissions: Record<Role, string[]>
  roles: RoleInfo[]
  members: Member[]
  invitations: Invitation[]

  switchboard: SwitchboardSnapshot
  /** Every call the mock knows (live lines, waiting calls and finished calls), keyed by call id. */
  calls: Record<string, CallDetail>
  transcripts: Record<string, Transcript> // by call id
  claimFiles: Record<string, ClaimFile> // by call id (live calls' files; finished calls' files are on the claim)
  timelines: Record<string, CallEvent[]> // by call id
  messages: Record<string, SmsMessage[]> // by call id
  /** Live lines and waiting calls (callId -> LiveLine), including those in the hand-off tray. */
  liveLines: Record<string, LiveLine>

  claims: Claim[] // newest first
  recordings: Record<string, Recording> // by claim id
  callRecordings: Record<string, Recording> // by call id (calls without a claim)
  photos: Record<string, Photo[]> // by claim id
  routing: Record<string, RoutingDecision> // by claim id
  siu: Record<string, SiuReferral> // by claim id

  qaQueue: QaQueueItem[]
  qaScores: Record<string, QaScore> // by call id

  routingChecks: RoutingChecks
  factSheets: Record<string, FactSheet> // by check key
  fairness: Record<string, Fairness> // by check key
  checks: Record<string, Check> // by check key

  scripts: Script[]
  consentRules: ConsentRule[]
  handoffRules: HandoffRules
  languages: Languages
  retention: Retention
  privacy: Privacy

  audit: AuditEntry[] // newest first

  photoLinks: Record<string, PhotoLinkInfo> // by token
}
