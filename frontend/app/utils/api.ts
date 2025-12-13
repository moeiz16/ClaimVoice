// Typed client for the ClaimVoice API (docs/API_CONTRACT.md Part 1). One function per endpoint the web app uses.
import type {
  Agreement, AuditEntry, CallDetail, CallEvent, ChainStatus, Check, Claim, ClaimFile, ClaimSummary, ConsentRule,
  FactSheet, Fairness, HandoffInfo, HandoffRules, Invitation, Languages, ListenOut, LiveLine, Me, Member, Meta, Page,
  Photo, PhotoLinkInfo, Privacy, QaQueueItem, QaScore, Recording, Retention, ReviewIn, Role, RoleInfo, Route,
  RoutingChecks, RoutingDecision, Script, ScriptQuestion, SessionState, SiuReferral, SmsMessage, StartCallIn,
  StartCallOut, Surge, SwitchboardSnapshot, TakeoverOut, Transcript, WhisperOut,
} from '~/types/api'
import { apiFetch, type RequestOpts } from './http'

type Q = RequestOpts['query']
const get = <T>(path: string, query?: Q) => apiFetch<T>(path, { query })
const post = <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: 'POST', body: body ?? {} })
const put = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: 'PUT', body })
const patch = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: 'PATCH', body })
const del = <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' })
const enc = encodeURIComponent

export const api = {
  meta: () => get<Meta>('/meta'),

  auth: {
    session: () => get<SessionState>('/auth/session'),
    login: (email: string, password: string) => post<Me>('/auth/login', { email, password }),
    demo: (role: Role) => post<Me>('/auth/demo', { role }),
    logout: () => post<void>('/auth/logout'),
    refresh: () => post<{ expiresAt: string, absoluteExpiresAt: string }>('/auth/refresh'),
    me: () => get<Me>('/auth/me'),
  },

  org: {
    members: () => get<Member[]>('/org/members'),
    updateMember: (id: string, body: { role?: Role, title?: string }) => patch<Member>(`/org/members/${enc(id)}`, body),
    invitations: () => get<Invitation[]>('/org/invitations'),
    invite: (email: string, role: Role) => post<Invitation>('/org/invitations', { email, role }),
    revokeInvitation: (id: string) => del<void>(`/org/invitations/${enc(id)}`),
    roles: () => get<RoleInfo[]>('/roles'),
  },

  calls: {
    live: (region?: string) => get<LiveLine[]>('/calls/live', { region }),
    get: (id: string) => get<CallDetail>(`/calls/${enc(id)}`),
    transcript: (id: string) => get<Transcript>(`/calls/${enc(id)}/transcript`),
    claimFile: (id: string) => get<ClaimFile>(`/calls/${enc(id)}/claim-file`),
    timeline: (id: string) => get<CallEvent[]>(`/calls/${enc(id)}/timeline`),
    messages: (id: string) => get<SmsMessage[]>(`/calls/${enc(id)}/messages`),
    recording: (id: string) => get<Recording>(`/calls/${enc(id)}/recording`),
    listen: (id: string) => post<ListenOut>(`/calls/${enc(id)}/listen`),
    stopListening: (id: string) => del<void>(`/calls/${enc(id)}/listen`),
    whisper: (id: string, text: string) => post<WhisperOut>(`/calls/${enc(id)}/whisper`, { text }),
    takeover: (id: string) => post<TakeoverOut>(`/calls/${enc(id)}/takeover`),
    say: (id: string, text: string) => post<{ turnId: string }>(`/calls/${enc(id)}/say`, { text }),
    giveBack: (id: string) => post<CallDetail>(`/calls/${enc(id)}/return`),
    handoff: (id: string, body: { reason: string, toUserId?: string | null, team?: 'intake' | 'adjusters' | 'siu' | null }) =>
      post<HandoffInfo>(`/calls/${enc(id)}/handoff`, body),
    acceptHandoff: (id: string) => post<{ handoff: HandoffInfo, listen: ListenOut }>(`/calls/${enc(id)}/handoff/accept`),
    hangup: (id: string, reason: string, note?: string) => post<CallDetail>(`/calls/${enc(id)}/hangup`, { reason, note }),
    startDemo: (body: StartCallIn) => post<StartCallOut>('/demo/calls', body),
  },

  switchboard: {
    snapshot: () => get<SwitchboardSnapshot>('/switchboard'),
    standby: (surgeId: string, note?: string) => post<Surge>(`/surges/${enc(surgeId)}/standby`, { note }),
    surgeQuestions: (surgeId: string, on: boolean) => post<Surge>(`/surges/${enc(surgeId)}/questions`, { on }),
  },

  claims: {
    list: (query: Q) => get<Page<ClaimSummary>>('/claims', query),
    get: (id: string) => get<Claim>(`/claims/${enc(id)}`),
    transcript: (id: string) => get<Transcript>(`/claims/${enc(id)}/transcript`),
    recording: (id: string) => get<Recording>(`/claims/${enc(id)}/recording`),
    photos: (id: string) => get<Photo[]>(`/claims/${enc(id)}/photos`),
    routing: (id: string) => get<RoutingDecision>(`/claims/${enc(id)}/routing`),
    acceptRoute: (id: string) => post<RoutingDecision>(`/claims/${enc(id)}/routing/accept`),
    overrideRoute: (id: string, route: Route, reason: string) => post<RoutingDecision>(`/claims/${enc(id)}/routing/override`, { route, reason }),
    siu: (id: string) => get<SiuReferral>(`/claims/${enc(id)}/siu`),
    editFile: (id: string, slots: { key: string, value: string, note: string }[]) => patch<ClaimFile>(`/claims/${enc(id)}/file`, { slots }),
  },

  qa: {
    queue: (query: Q) => get<Page<QaQueueItem>>('/qa/queue', query),
    score: (callId: string) => get<QaScore>(`/qa/calls/${enc(callId)}`),
    review: (callId: string, body: ReviewIn) => post<QaScore>(`/qa/calls/${enc(callId)}/review`, body),
    agreement: () => get<Agreement>('/qa/agreement'),
  },

  routing: {
    checks: () => get<RoutingChecks>('/routing-checks'),
    factSheet: (key: string) => get<FactSheet>(`/routing-checks/${enc(key)}`),
    fairness: (key: string, version?: number) => get<Fairness>(`/routing-checks/${enc(key)}/fairness`, { version }),
    signOff: (key: string, version: number, note: string) => post<Check>(`/routing-checks/${enc(key)}/versions/${version}/sign-off`, { version, note }),
    regulatorPackUrl: () => '/api/v1/routing-checks/regulator-pack',
  },

  settings: {
    scripts: () => get<Script[]>('/settings/scripts'),
    saveScript: (lossType: string, questions: ScriptQuestion[], note: string) => put<Script>(`/settings/scripts/${enc(lossType)}`, { questions, note }),
    consentRules: () => get<ConsentRule[]>('/settings/consent-rules'),
    saveConsentRule: (region: string, body: Pick<ConsentRule, 'rule' | 'announcement'>) => put<ConsentRule>(`/settings/consent-rules/${enc(region)}`, body),
    handoffRules: () => get<HandoffRules>('/settings/handoff-rules'),
    saveHandoffRules: (body: HandoffRules) => put<HandoffRules>('/settings/handoff-rules', body),
    languages: () => get<Languages>('/settings/languages'),
    saveLanguages: (body: Languages) => put<Languages>('/settings/languages', body),
    retention: () => get<Retention>('/settings/retention'),
    saveRetention: (body: Retention) => put<Retention>('/settings/retention', body),
    privacy: () => get<Privacy>('/settings/privacy'),
    savePrivacy: (body: Privacy) => put<Privacy>('/settings/privacy', body),
  },

  audit: {
    list: (query: Q) => get<Page<AuditEntry>>('/audit', query),
    verify: () => get<ChainStatus>('/audit/verify'),
    exportUrl: (query: Q) => `/api/v1/audit/export.csv${query ? `?${new URLSearchParams(Object.entries(query).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])).toString()}` : ''}`,
  },

  photoLinks: {
    get: (token: string) => get<PhotoLinkInfo>(`/photo-links/${enc(token)}`),
    upload: (token: string, file: File, caption?: string) => {
      const form = new FormData()
      form.append('file', file)
      if (caption) form.append('caption', caption)
      return apiFetch<Photo>(`/photo-links/${enc(token)}/photos`, { method: 'POST', body: form, bearer: undefined })
    },
  },
}

export type Api = typeof api
