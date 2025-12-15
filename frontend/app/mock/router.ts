// The local mock API: every endpoint the web app uses, answered from the seed in ./seed.ts with the same shapes and
// rules as the real API (permissions, 404 for unknown ids, RFC 7807 errors, X-ClaimVoice-Now). Switched on with
// NUXT_PUBLIC_API_MOCK=1; never used otherwise.
import type {
  AuditEntry, CallDetail, Claim, ClaimSummary, HandoffInfo, LiveLine, Me, Page, Photo, Problem, QaScore, Role,
  Route, SessionState, Slot, Turn,
} from '~/types/api'
import type { MockBackend, MockResponse } from '~/utils/http'
import type { StreamHandle, StreamOptions } from '~/utils/sse'
import type { MockDb } from './db'
import { buildSeed } from './seed'
import { MockStreams } from './streams'

const ROUTE_LABEL: Record<Route, string> = { fast_track: 'Fast-track', adjuster: 'Adjuster', special_investigation: 'Closer look' }

export class MockServer {
  db: MockDb
  private bootedAt = Date.now()
  private userId: string | null = null
  readonly streams: MockStreams
  private seq = 0

  constructor(db: MockDb = buildSeed()) {
    this.db = db
    this.streams = new MockStreams(this)
    try { this.userId = sessionStorage.getItem('cv-mock-user') } catch { /* no storage */ }
  }

  /** Demo time: the seed's "now" plus real time since the mock started. */
  now(): Date { return new Date(this.db.now.getTime() + (Date.now() - this.bootedAt)) }
  nowIso(): string { return this.now().toISOString() }

  private setUser(id: string | null) {
    this.userId = id
    try {
      if (id) sessionStorage.setItem('cv-mock-user', id)
      else sessionStorage.removeItem('cv-mock-user')
    } catch { /* no storage */ }
  }

  person() { return this.db.people.find(p => p.userId === this.userId) ?? null }

  me(): Me | null {
    const p = this.person()
    if (!p) return null
    const clock = this.clock()
    return {
      user: { id: p.userId, email: p.email, fullName: p.fullName, preferredLanguage: 'en', avatarColor: p.avatarColor, createdAt: '2025-12-01T16:00:00Z' },
      activeOrg: { id: this.db.orgId, name: 'Larkspur Mutual', slug: 'larkspur-mutual', timezone: 'America/Edmonton', regions: ['CA-AB', 'US-CO', 'CA-QC'], languages: ['en', 'fr'], isSample: true, createdAt: '2025-12-01T16:00:00Z' },
      membership: { role: p.role, roleLabel: p.roleLabel, title: p.title, permissions: this.db.permissions[p.role] },
      orgs: [{ id: this.db.orgId, name: 'Larkspur Mutual', slug: 'larkspur-mutual', role: p.role, roleLabel: p.roleLabel, isSample: true }],
      session: { expiresAt: new Date(Date.now() + 30 * 60_000).toISOString(), absoluteExpiresAt: new Date(Date.now() + 12 * 3600_000).toISOString() },
      clock,
    }
  }

  clock() {
    return { today: '2026-01-08', now: this.nowIso(), demo: true, timezone: 'America/Edmonton' }
  }

  can(perm: string): boolean {
    const p = this.person()
    return !!p && this.db.permissions[p.role].includes(perm)
  }

  audit(actionLabel: string, action: string, summary: string, target?: { type: string, id: string, label: string }) {
    const p = this.person()
    const entry: AuditEntry = {
      id: `mock-audit-${++this.seq}`,
      seq: (this.db.audit[0]?.seq ?? 0) + 1,
      at: this.nowIso(),
      actorLabel: p?.fullName ?? 'Someone',
      action,
      actionLabel,
      targetType: target?.type ?? null,
      targetId: target?.id ?? null,
      targetLabel: target?.label ?? null,
      summary,
      details: {},
    }
    this.db.audit.unshift(entry)
  }

  timeLabel(): string {
    const d = this.now()
    const local = new Date(d.getTime() - 7 * 3600_000)
    const h = local.getUTCHours()
    const m = local.getUTCMinutes()
    return `${h % 12 === 0 ? 12 : h % 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'a.m.' : 'p.m.'}`
  }

  // ------------------------------------------------------------------ requests
  async handle(method: string, path: string, q: URLSearchParams, body: unknown): Promise<MockResponse> {
    await new Promise(r => setTimeout(r, 60 + Math.random() * 90))
    const headers = { 'X-ClaimVoice-Now': this.nowIso() }
    try {
      const out = this.route(method, path, q, (body ?? {}) as Record<string, unknown>)
      return { status: out === undefined ? 204 : 200, body: out, headers }
    }
    catch (e) {
      if (e instanceof MockProblem) return { status: e.status, body: e.problem, headers }
      throw e
    }
  }

  private need(perm: string) {
    if (!this.person()) throw problem(401, 'not_authenticated', 'Please sign in.')
    if (!this.can(perm)) throw problem(403, 'forbidden', 'You do not have access to this.')
  }

  private route(method: string, path: string, q: URLSearchParams, body: Record<string, unknown>): unknown {
    const db = this.db
    const m = (re: RegExp) => path.match(re)
    let r: RegExpMatchArray | null

    // ---------- public
    if (method === 'GET' && path === '/meta') return db.meta
    if (method === 'GET' && path === '/auth/csrf') return undefined
    if (method === 'GET' && path === '/auth/session') return { me: this.me(), clock: this.clock() } satisfies SessionState
    if (method === 'POST' && path === '/auth/login') {
      const email = String(body.email ?? '').toLowerCase().trim()
      const p = db.people.find(x => x.email === email)
      if (!p || String(body.password ?? '') !== 'larkspur-demo-2026') throw problem(401, 'invalid_credentials', 'That email and password don\'t match.')
      this.setUser(p.userId)
      this.audit('signed in', 'auth.login', `${p.fullName} signed in.`)
      return this.me()
    }
    if (method === 'POST' && path === '/auth/demo') {
      const role = String(body.role) as Role
      const id = db.demoPeople[role]
      if (!id) throw problem(404, 'not_found', 'No sample person for that role.')
      this.setUser(id)
      return this.me()
    }
    if (method === 'POST' && path === '/auth/logout') { this.setUser(null); return undefined }
    if (method === 'POST' && path === '/auth/refresh') return this.me()?.session
    if (method === 'GET' && path === '/auth/me') { this.need('lines:read'); return this.me() }

    if ((r = m(/^\/photo-links\/([^/]+)$/)) && method === 'GET') {
      const link = db.photoLinks[r[1]!]
      if (!link) throw problem(404, 'not_found', 'This photo link was not found.')
      if (Date.parse(link.expiresAt) < this.now().getTime()) throw problem(410, 'expired', 'This photo link has expired.')
      return link
    }
    if ((r = m(/^\/photo-links\/([^/]+)\/photos$/)) && method === 'POST') {
      const link = db.photoLinks[r[1]!]
      if (!link) throw problem(404, 'not_found', 'This photo link was not found.')
      if (link.uploaded >= link.maxPhotos) throw problem(422, 'validation_error', 'That is the most photos this link takes.')
      link.uploaded += 1
      const photo: Photo = { id: `mock-photo-${++this.seq}`, url: '', thumbnailUrl: '', caption: null, receivedAt: this.nowIso(), source: 'text_link', width: 1200, height: 900 }
      return photo
    }
    if (method === 'POST' && path === '/demo/calls') return this.streams.startDemoCall(body)

    // ---------- org
    if (method === 'GET' && path === '/org/members') {
      this.need('members:read')
      return db.members.map(x => ({ ...x, isYou: x.userId === this.userId }))
    }
    if ((r = m(/^\/org\/members\/([^/]+)$/)) && method === 'PATCH') {
      this.need('members:manage')
      const mem = db.members.find(x => x.membershipId === r![1])
      if (!mem) throw problem(404, 'not_found', 'Not found.')
      if (body.role) {
        const role = body.role as Role
        if (mem.role === 'admin' && role !== 'admin' && db.members.filter(x => x.role === 'admin').length === 1)
          throw problem(409, 'last_admin', 'Larkspur needs at least one administrator.')
        mem.role = role
        mem.roleLabel = db.roles.find(x => x.role === role)?.label ?? role
        this.audit('changed a role', 'member.role_changed', `${this.person()?.fullName} made ${mem.fullName} ${mem.roleLabel.toLowerCase()}.`)
      }
      return mem
    }
    if (method === 'GET' && path === '/org/invitations') { this.need('members:manage'); return db.invitations }
    if (method === 'POST' && path === '/org/invitations') {
      this.need('members:manage')
      const email = String(body.email ?? '').trim()
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw problem(422, 'validation_error', 'One or more fields are invalid.', [{ field: 'email', message: 'Enter a work email address.' }])
      const role = body.role as Role
      const inv = { id: `mock-inv-${++this.seq}`, email, role, roleLabel: db.roles.find(x => x.role === role)?.label ?? role, invitedBy: this.person()?.fullName ?? null, createdAt: this.nowIso(), expiresAt: new Date(this.now().getTime() + 7 * 86_400_000).toISOString(), status: 'pending' as const }
      db.invitations.unshift(inv)
      this.audit('invited', 'invitation.created', `${this.person()?.fullName} invited ${email} as ${inv.roleLabel.toLowerCase()}.`)
      return inv
    }
    if ((r = m(/^\/org\/invitations\/([^/]+)$/)) && method === 'DELETE') {
      this.need('members:manage')
      const inv = db.invitations.find(x => x.id === r![1])
      if (inv) inv.status = 'revoked'
      return undefined
    }
    if (method === 'GET' && path === '/roles') { this.need('members:read'); return db.roles }

    // ---------- switchboard
    if (method === 'GET' && path === '/switchboard') { this.need('lines:read'); return this.snapshot() }
    if (method === 'GET' && path === '/calls/live') {
      this.need('lines:read')
      const region = q.get('region')
      return db.switchboard.lines.filter(l => !region || l.region === region)
    }
    if ((r = m(/^\/surges\/([^/]+)\/standby$/)) && method === 'POST') {
      this.need('lines:manage')
      const s = db.switchboard.surge
      if (!s || s.id !== r[1]) throw problem(404, 'not_found', 'Not found.')
      s.standbyCalled = true
      s.waitForPersonSeconds = 30
      const names = ['Marc Dufresne', 'Hana Okafor']
      for (const [i, name] of names.entries()) db.switchboard.freePeople.push({ id: `standby-${i}`, name })
      this.audit('called in the standby team', 'surge.standby_called', `${this.person()?.fullName} called in the standby team (2) for the Chinook windstorm.`)
      this.streams.emitOrg('surge.updated', s)
      return s
    }
    if ((r = m(/^\/surges\/([^/]+)\/questions$/)) && method === 'POST') {
      this.need('lines:manage')
      const s = db.switchboard.surge
      if (!s) throw problem(404, 'not_found', 'Not found.')
      s.surgeQuestionsOn = !!body.on
      this.audit('changed the surge questions', 'surge.questions', `${this.person()?.fullName} switched wind questions ${s.surgeQuestionsOn ? 'on' : 'off'}.`)
      return s
    }

    // ---------- calls
    if ((r = m(/^\/calls\/([^/]+)(\/[a-z-]+(?:\/[a-z]+)?)?$/))) {
      const id = r[1]!
      const sub = r[2] ?? ''
      if (id === 'live') return undefined
      const call = db.calls[id]
      if (!call) throw problem(404, 'not_found', 'Not found.')
      return this.callRoute(method, call, sub, body)
    }

    // ---------- claims
    if (method === 'GET' && path === '/claims') { this.need('claims:read'); return this.claimList(q) }
    if ((r = m(/^\/claims\/([^/]+)(\/[a-z-]+(?:\/[a-z]+)?)?$/))) {
      const claim = db.claims.find(c => c.id === r![1])
      if (!claim) throw problem(404, 'not_found', 'Not found.')
      return this.claimRoute(method, claim, r[2] ?? '', body)
    }

    // ---------- quality
    if (method === 'GET' && path === '/qa/queue') {
      this.need('qa:read')
      const status = q.get('status') ?? 'needs_review'
      const item = q.get('item')
      let items = db.qaQueue.filter(x => status === 'all' || x.status === status)
      if (item) items = items.filter(x => db.qaScores[x.callId]?.items.some(i => i.key === item && i.passed === false))
      return page(items, q)
    }
    if ((r = m(/^\/qa\/calls\/([^/]+)$/)) && method === 'GET') {
      this.need('qa:read')
      const s = db.qaScores[r[1]!]
      if (!s) throw problem(404, 'not_found', 'Not found.')
      return s
    }
    if ((r = m(/^\/qa\/calls\/([^/]+)\/review$/)) && method === 'POST') {
      this.need('qa:review')
      const s = db.qaScores[r[1]!]
      if (!s) throw problem(404, 'not_found', 'Not found.')
      return this.review(s, body)
    }
    if (method === 'GET' && path === '/qa/agreement') {
      this.need('qa:read')
      return { reviewedCalls: 24, overall: 0.92, cohenKappa: 0.81, byItem: [] }
    }

    // ---------- routing checks
    if (method === 'GET' && path === '/routing-checks') { this.need('models:read'); return db.routingChecks }
    if ((r = m(/^\/routing-checks\/(size|closer_look)$/)) && method === 'GET') { this.need('models:read'); return db.factSheets[r[1]!] }
    if ((r = m(/^\/routing-checks\/(size|closer_look)\/fairness$/)) && method === 'GET') { this.need('models:read'); return db.fairness[r[1]!] }
    if ((r = m(/^\/routing-checks\/(size|closer_look)\/versions\/(\d+)\/sign-off$/)) && method === 'POST') {
      this.need('models:signoff')
      return this.signOff(r[1]!, Number(r[2]), String(body.note ?? ''))
    }

    // ---------- settings
    if (path.startsWith('/settings')) return this.settingsRoute(method, path, body)

    // ---------- audit
    if (method === 'GET' && path === '/audit') {
      this.need('audit:read')
      const action = q.get('action')
      const actor = q.get('actor')
      const target = q.get('target')
      let items = db.audit
      if (action) items = items.filter(a => a.action.startsWith(action))
      if (actor) { const name = db.people.find(p => p.userId === actor)?.fullName ?? actor; items = items.filter(a => a.actorLabel === name) }
      if (target) items = items.filter(a => (a.targetLabel ?? '').includes(target) || a.summary.includes(target))
      return page(items, q, 50)
    }
    if (method === 'GET' && path === '/audit/verify') {
      this.need('audit:read')
      return { ok: true, checked: db.audit.length, firstBrokenSeq: null, reason: null, checkedAt: new Date(this.now().getTime() - 120_000).toISOString() }
    }

    throw problem(404, 'not_found', 'Not found.')
  }

  snapshot() {
    const db = this.db
    const lines = db.switchboard.lines
    const waiting = db.switchboard.handoffTray.filter(h => h.state === 'waiting')
    db.switchboard.caption = `Larkspur Mutual · Thursday 8 January · ${this.timeLabel()} Calgary time · ${lines.length} on the line, ${waiting.length} waiting for a person`
    return { ...db.switchboard, lines: [...lines], handoffTray: [...db.switchboard.handoffTray] }
  }

  private callRoute(method: string, call: CallDetail, sub: string, body: Record<string, unknown>): unknown {
    const db = this.db
    const id = call.id
    if (method === 'GET') {
      this.need('calls:read')
      if (sub === '') return call
      if (sub === '/transcript') return db.transcripts[id] ?? { callId: id, language: call.language, retained: true, notice: null, turns: [] }
      if (sub === '/claim-file') {
        const file = db.claimFiles[id] ?? db.claims.find(c => c.callId === id)?.file
        if (!file) throw problem(404, 'not_found', 'Not found.')
        return file
      }
      if (sub === '/timeline') return db.timelines[id] ?? []
      if (sub === '/messages') return db.messages[id] ?? []
      if (sub === '/recording') {
        this.need('recordings:read')
        const claim = db.claims.find(c => c.callId === id)
        const rec = (claim && db.recordings[claim.id]) || db.callRecordings[id]
        if (!rec) throw problem(404, 'not_found', 'Not found.')
        return rec
      }
    }
    if (method === 'POST' && sub === '/listen') {
      this.need('calls:listen')
      this.setListener(call, 'listening')
      this.audit('started listening to', 'call.listen', `${this.person()?.fullName} started listening to ${call.lineLabel ?? 'a line'} (${call.callerLabel}) at ${this.timeLabel()}.`)
      return { mode: 'transcript', connect: null }
    }
    if (method === 'DELETE' && sub === '/listen') {
      this.need('calls:listen')
      this.setListener(call, null)
      return undefined
    }
    if (method === 'POST' && sub === '/whisper') {
      this.need('calls:whisper')
      const text = String(body.text ?? '').trim()
      if (!text) throw problem(422, 'validation_error', 'One or more fields are invalid.', [{ field: 'text', message: 'Write a short note for ClaimVoice.' }])
      if (text.length > 280) throw problem(422, 'validation_error', 'One or more fields are invalid.', [{ field: 'text', message: 'Keep it under 280 characters.' }])
      if (call.state === 'ended') throw problem(409, 'call_not_live', 'This call has ended.')
      this.audit('whispered to ClaimVoice on', 'call.whisper', `${this.person()?.fullName} whispered to ClaimVoice on ${call.lineLabel ?? 'a line'}: "${text}"`)
      return this.streams.whisper(call, text)
    }
    if (method === 'POST' && sub === '/takeover') {
      this.need('calls:takeover')
      if (call.listeners.some(l => l.mode === 'took_over' && l.userId !== this.userId)) throw problem(409, 'already_taken', 'Someone else already has this call.')
      this.setListener(call, 'took_over')
      call.state = 'with_person'
      call.stateLabel = 'With a person'
      this.audit('took over', 'call.takeover', `${this.person()?.fullName} took over ${call.lineLabel ?? 'a line'} (${call.callerLabel}) at ${this.timeLabel()}.`, { type: 'call', id: call.id, label: `${call.lineLabel} (${call.callerLabel})` })
      this.streams.takeover(call)
      return { call, connect: null }
    }
    if (method === 'POST' && sub === '/say') {
      this.need('calls:takeover')
      return this.streams.say(call, String(body.text ?? ''))
    }
    if (method === 'POST' && sub === '/return') {
      this.need('calls:takeover')
      this.setListener(call, 'listening')
      call.state = 'with_line'
      call.stateLabel = 'With ClaimVoice'
      this.audit('handed back', 'call.returned', `${this.person()?.fullName} handed ${call.lineLabel ?? 'a line'} back to ClaimVoice.`)
      this.streams.giveBack(call)
      return call
    }
    if (method === 'POST' && sub === '/handoff') {
      this.need('calls:handoff')
      return this.streams.handoff(call, String(body.reason ?? ''), (body.team as HandoffInfo['team']) ?? 'intake')
    }
    if (method === 'POST' && sub === '/handoff/accept') {
      this.need('calls:handoff')
      const h = db.switchboard.handoffTray.find(x => x.callId === call.id)
      if (!h) throw problem(404, 'not_found', 'Not found.')
      if (h.state !== 'waiting') throw problem(409, 'already_taken', 'Someone else already took this call.')
      const p = this.person()!
      h.state = 'accepted'
      h.acceptedBy = { id: p.userId, name: p.fullName }
      h.acceptedAt = this.nowIso()
      db.switchboard.handoffTray = db.switchboard.handoffTray.filter(x => x.id !== h.id)
      const line = db.liveLines[call.id]
      if (line) {
        line.state = 'with_person'
        line.stateLabel = 'With a person'
        line.handoff = h
        line.listeners = [{ userId: p.userId, name: p.fullName, mode: 'took_over' }]
        if (!db.switchboard.lines.some(l => l.callId === call.id)) db.switchboard.lines.push(line)
      }
      call.listeners = [{ userId: p.userId, name: p.fullName, mode: 'took_over' }]
      call.state = 'with_person'
      this.audit('took the call', 'call.handoff_accepted', `${p.fullName} took ${h.lineLabel} (${h.callerLabel}) from the hand-off tray at ${this.timeLabel()}.`)
      this.streams.emitOrg('handoff.updated', h)
      if (line) this.streams.emitOrg('line.updated', line)
      return { handoff: h, listen: { mode: 'transcript', connect: null } }
    }
    if (method === 'POST' && sub === '/hangup') {
      this.need('calls:hangup')
      call.state = 'ended'
      return call
    }
    throw problem(404, 'not_found', 'Not found.')
  }

  private setListener(call: CallDetail, mode: 'listening' | 'took_over' | null) {
    const p = this.person()
    if (!p) return
    const others = call.listeners.filter(l => l.userId !== p.userId)
    call.listeners = mode ? [...others, { userId: p.userId, name: p.fullName, mode }] : others
    const line = this.db.liveLines[call.id]
    if (line) {
      line.listeners = call.listeners
      if (mode === 'took_over') { line.state = 'with_person'; line.stateLabel = 'With a person' }
      this.streams.emitOrg('line.updated', line)
    }
    this.streams.emitCall(call.id, 'listener.changed', { listeners: call.listeners })
  }

  private claimList(q: URLSearchParams): Page<ClaimSummary> {
    let items: ClaimSummary[] = this.db.claims.map(c => this.visibleClaim(c))
    const route = q.get('route')
    const status = q.get('status')
    const query = (q.get('q') ?? '').toLowerCase().trim()
    const flag = q.get('flag')
    const assigned = q.get('assigned')
    if (route && route !== 'all') items = items.filter(c => c.route?.route === route || (route === 'special_investigation' && c.siuOpen))
    if (status && status !== 'all') items = items.filter(c => c.status === status)
    if (flag === 'urgent_safety') items = items.filter(c => c.urgentSafety)
    if (flag === 'siu') items = items.filter(c => c.siuOpen)
    if (assigned === 'me') items = items.filter(c => c.assignedTo?.id === this.userId)
    if (query) items = items.filter(c => `${c.claimNumber} ${c.holderName} ${c.lossPlace ?? ''} ${c.policyNumber}`.toLowerCase().includes(query))
    return page(items, q)
  }

  private visibleClaim<T extends ClaimSummary>(c: T): T {
    if (this.can('siu:read')) return c
    return { ...c, siuOpen: false }
  }

  private claimRoute(method: string, claim: Claim, sub: string, body: Record<string, unknown>): unknown {
    const db = this.db
    if (method === 'GET') {
      this.need('claims:read')
      if (sub === '') return this.visibleClaim(claim)
      if (sub === '/transcript') return (claim.callId && db.transcripts[claim.callId]) || { callId: claim.callId, language: claim.language, retained: true, notice: null, turns: [] }
      if (sub === '/recording') {
        this.need('recordings:read')
        return db.recordings[claim.id] ?? { available: false, reason: 'The caller did not agree to recording', audioUrl: null, durationSeconds: null, peaks: null, segments: [], moments: [], hushes: [], retainedUntil: null }
      }
      if (sub === '/photos') return db.photos[claim.id] ?? []
      if (sub === '/routing') {
        const rd = db.routing[claim.id]
        if (!rd) throw problem(404, 'not_found', 'Not found.')
        return this.can('siu:read') ? rd : { ...rd, fraud: null, signs: null }
      }
      if (sub === '/siu') {
        this.need('siu:read')
        const s = db.siu[claim.id]
        if (!s) throw problem(404, 'not_found', 'Not found.')
        return s
      }
    }
    if (method === 'POST' && sub === '/routing/accept') {
      this.need('claims:route')
      const rd = db.routing[claim.id]!
      const p = this.person()!
      rd.acceptedBy = { id: p.userId, name: p.fullName }
      rd.acceptedAt = this.nowIso()
      this.audit('accepted the route of', 'claim.route_accepted', `${p.fullName} accepted the route of ${claim.claimNumber}: ${rd.routeLabel}.`, { type: 'claim', id: claim.id, label: claim.claimNumber })
      return rd
    }
    if (method === 'POST' && sub === '/routing/override') {
      this.need('claims:route')
      const route = body.route as Route
      const reason = String(body.reason ?? '').trim()
      if (!reason) throw problem(422, 'validation_error', 'One or more fields are invalid.', [{ field: 'reason', message: 'Give a reason for the change.' }])
      const rd = db.routing[claim.id]!
      const p = this.person()!
      const from = rd.routeLabel
      rd.override = { route, reason, by: { id: p.userId, name: p.fullName }, at: this.nowIso() }
      rd.route = route
      rd.routeLabel = ROUTE_LABEL[route]
      claim.route = { route, label: ROUTE_LABEL[route], decidedBy: 'person', topReason: reason }
      this.audit('changed the route', 'claim.route_override', `${p.fullName} changed the route of ${claim.claimNumber} from ${from} to ${rd.routeLabel}: '${reason}'`, { type: 'claim', id: claim.id, label: claim.claimNumber })
      return rd
    }
    if (method === 'PATCH' && sub === '/file') {
      this.need('claims:edit')
      const p = this.person()!
      for (const e of (body.slots as { key: string, value: string, note: string }[]) ?? []) {
        for (const sec of claim.file.sections) {
          const s: Slot | undefined = sec.slots.find(x => x.key === e.key)
          if (!s) continue
          s.history = [{ value: s.value, display: s.display, source: s.source, changedBy: null, at: this.nowIso(), span: s.span, note: null }, ...s.history]
          s.value = e.value
          s.display = e.value
          s.source = 'person'
          s.sourceLabel = `edited by ${p.fullName}`
        }
      }
      this.audit('edited the claim file of', 'claim.file_edited', `${p.fullName} edited the claim file of ${claim.claimNumber}.`)
      return claim.file
    }
    throw problem(404, 'not_found', 'Not found.')
  }

  private review(s: QaScore, body: Record<string, unknown>): QaScore {
    const p = this.person()!
    const items = (body.items as { key: string, verdict: 'agree' | 'disagree', note?: string }[]) ?? []
    for (const v of items) {
      const it = s.items.find(x => x.key === v.key)
      if (it) { it.reviewerVerdict = v.verdict; it.reviewerNote = v.note ?? null }
    }
    s.status = 'reviewed'
    s.reviewedBy = { id: p.userId, name: p.fullName }
    s.reviewedAt = this.nowIso()
    s.reviewNote = (body.coachingNote as string) || (body.note as string) || null
    const q = this.db.qaQueue.find(x => x.callId === s.callId)
    if (q) { q.status = 'reviewed'; q.reviewer = { id: p.userId, name: p.fullName } }
    this.audit('reviewed', 'qa.review', `${p.fullName} reviewed the call quality of ${q?.reference ?? 'a call'}.`)
    return s
  }

  private signOff(key: string, version: number, note: string) {
    const check = this.db.checks[key]
    if (!check) throw problem(404, 'not_found', 'Not found.')
    const v = check.candidate?.version === version ? check.candidate : check.inUse.version === version ? check.inUse : null
    if (!v) throw problem(404, 'not_found', 'Not found.')
    const p = this.person()!
    const side = p.role === 'supervisor' ? 'claims' : 'model_risk'
    const so = v.signOffs.find(x => x.side === side)
    if (!so) throw problem(404, 'not_found', 'Not found.')
    if (so.state === 'signed') throw problem(409, 'already_signed', 'This side has already signed.')
    if (v.signOffs.some(x => x.state === 'signed' && x.by?.id === p.userId)) throw problem(409, 'already_signed', 'Two different people must sign.')
    so.state = 'signed'
    so.by = { id: p.userId, name: p.fullName }
    so.at = this.nowIso()
    so.note = note
    const q = this.db.routingChecks.questions.find(x => x.key === 'replace')
    const qs = q?.signOffs?.find(x => x.side === side)
    if (qs) Object.assign(qs, so)
    this.audit('signed off', 'check.signed_off', `${p.fullName} signed off ${check.name} version ${version} for ${side === 'claims' ? 'claims' : 'model risk'}.`)
    return check
  }

  private settingsRoute(method: string, path: string, body: Record<string, unknown>): unknown {
    const db = this.db
    const write = method === 'PUT'
    this.need(write ? 'settings:manage' : 'settings:read')
    const who = this.person()?.fullName
    if (path === '/settings/scripts' && method === 'GET') return db.scripts
    const sr = path.match(/^\/settings\/scripts\/([a-z_]+)$/)
    if (sr) {
      const s = db.scripts.find(x => x.lossType === sr[1])
      if (!s) throw problem(404, 'not_found', 'Not found.')
      if (write) {
        s.questions = body.questions as typeof s.questions
        s.version += 1
        s.updatedAt = this.nowIso()
        const p = this.person()!
        s.updatedBy = { id: p.userId, name: p.fullName }
        this.audit('changed a script', 'settings.script', `${who} changed the ${s.lossTypeLabel.toLowerCase()} script (version ${s.version}).`)
      }
      return s
    }
    if (path === '/settings/consent-rules') return db.consentRules
    const cr = path.match(/^\/settings\/consent-rules\/([A-Z-]+)$/)
    if (cr && write) {
      const rule = db.consentRules.find(x => x.region === cr[1])
      if (!rule) throw problem(404, 'not_found', 'Not found.')
      if (rule.rule === 'all_party' && body.rule === 'one_party') throw problem(422, 'validation_error', 'This state requires everyone on the call to agree. It can\'t be weakened.')
      rule.announcement = body.announcement as typeof rule.announcement
      rule.isDefault = false
      this.audit('changed a consent rule', 'settings.consent', `${who} changed the consent sentence for ${rule.regionLabel}.`)
      return rule
    }
    const simple: Record<string, keyof MockDb> = {
      '/settings/handoff-rules': 'handoffRules', '/settings/languages': 'languages', '/settings/retention': 'retention', '/settings/privacy': 'privacy',
    }
    const k = simple[path]
    if (k) {
      if (write) {
        Object.assign(db[k] as object, body)
        this.audit('changed settings', `settings.${String(k)}`, `${who} changed the ${({ handoffRules: 'hand-off rules', languages: 'language settings', retention: 'retention settings', privacy: 'privacy contact' } as Record<string, string>)[k]}.`)
      }
      return db[k]
    }
    if (path === '/settings') return { languages: db.languages, retention: db.retention, handoffRules: db.handoffRules, privacy: db.privacy, consentRules: db.consentRules.length, scripts: db.scripts.length }
    throw problem(404, 'not_found', 'Not found.')
  }

  // used by the streams module
  findLine(callId: string): LiveLine | undefined { return this.db.liveLines[callId] }
  appendTurn(callId: string, turn: Turn) {
    const t = this.db.transcripts[callId]
    if (t) t.turns.push(turn)
  }
}

class MockProblem extends Error {
  constructor(readonly status: number, readonly problem: Problem) { super(problem.title) }
}

function problem(status: number, code: string, detail: string, errors?: { field: string, message: string }[]): MockProblem {
  return new MockProblem(status, { type: `https://claimvoice.dev/problems/${code}`, title: detail, status, code, detail, errors: errors ?? null, requestId: 'mock' })
}

function page<T>(items: T[], q: URLSearchParams, defaultSize = 25): Page<T> {
  const pageNo = Math.max(1, Number(q.get('page') ?? 1))
  const size = Math.min(100, Math.max(1, Number(q.get('pageSize') ?? defaultSize)))
  return { items: items.slice((pageNo - 1) * size, pageNo * size), page: pageNo, pageSize: size, total: items.length, totalPages: Math.max(1, Math.ceil(items.length / size)) }
}

let server: MockServer | null = null
export function mockServer(): MockServer {
  if (!server) server = new MockServer()
  return server
}

export function createMockBackend(): MockBackend {
  const s = mockServer()
  return {
    fetch: (method, path, query, body) => s.handle(method, path, query, body),
    stream: (path: string, opts: StreamOptions): StreamHandle => s.streams.open(path, opts),
  }
}
