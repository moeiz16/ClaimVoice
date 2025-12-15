// Simulated server-sent events for the mock API: the org stream (/switchboard/stream) and per-call streams
// (/calls/{id}/stream). Live lines carry on with a short scripted continuation, so the line desk and the live call
// view move like the real thing; whispers are acted on at ClaimVoice's next turn; take-over adds a person's voice.
import type { CallDetail, HandoffInfo, LiveLine, Slot, StageInfo, Turn } from '~/types/api'
import type { StreamHandle, StreamOptions } from '~/utils/sse'
import type { MockServer } from './router'

interface Sub { path: string, opts: StreamOptions }
interface Step { delay: number, speaker: 'caller' | 'line', text: string, slots?: Partial<Slot>[], stage?: Partial<StageInfo>, heard?: { key: string, text: string }, asked?: string }

const STEPS = ['Consent', 'Policy', 'Safety', 'What happened', 'Photos', 'Coverage', 'Read-back']
function stageFor(step: number, key: string, label: string): StageInfo {
  return { key, label, step, stepLabel: STEPS[step - 1]!, steps: 7, nextLabel: STEPS[step] ? `${STEPS[step]} next` : null }
}

/** What happens next on the three seeded live lines (by line label). */
const CONTINUATIONS: Record<string, Step[]> = {
  'Line 1': [
    { delay: 6000, speaker: 'line', text: 'Thanks, Gord. I\'ll note the garage skylight as possibly cracked, and the adjuster can check it. Is the siding damage on the north wall only?', asked: 'Is the siding damage on the north wall only?' },
    { delay: 9000, speaker: 'caller', text: 'Mostly the north wall, and a bit around the back door.', slots: [{ key: 'siding_or_fence_damage', label: 'Siding', display: 'North wall and by the back door' }], heard: { key: 'siding', text: 'Siding torn, north wall' } },
    { delay: 7000, speaker: 'line', text: 'Got it. I\'m texting you a link for photos of the roof, the siding and both skylights. Take them when it\'s light and safe.', stage: stageFor(5, 'photos', 'Photos'), asked: 'I\'m texting you a link for photos.' },
    { delay: 6000, speaker: 'caller', text: 'Okay, I see the text.', slots: [{ key: 'photo_link_sent_to', label: 'Photo link', display: 'Sent by text' }] },
  ],
  'Line 2': [
    { delay: 7000, speaker: 'line', text: 'Thank you. Is your car safe to drive, or does it need a tow?', asked: 'Is your car safe to drive, or does it need a tow?' },
    { delay: 9000, speaker: 'caller', text: 'The bumper\'s hanging off. I don\'t think I should drive it.', slots: [{ key: 'vehicle_drivable', label: 'Drivable', display: 'No, bumper hanging off' }], heard: { key: 'tow', text: 'Needs a tow' } },
    { delay: 7000, speaker: 'line', text: 'Then I\'ll arrange a tow. Did the police come, or did you file a report?', asked: 'Did the police come, or did you file a report?' },
  ],
  'Line 3': [
    { delay: 8000, speaker: 'line', text: 'Oui, vous pouvez appeler un plombier tout de suite. Gardez la facture pour l\'expert.', asked: 'Oui, vous pouvez appeler un plombier tout de suite.' },
    { delay: 8000, speaker: 'caller', text: 'Parfait, merci. J\'appelle mon beau-frère, il est plombier.', heard: { key: 'plumber', text: 'Plombier en route' } },
    { delay: 7000, speaker: 'line', text: 'Très bien. Vous êtes couverte pour les dégâts d\'eau soudains. La franchise est de 1 000 $.', stage: stageFor(6, 'coverage', 'Coverage basics'), asked: 'Vous êtes couverte pour les dégâts d\'eau soudains.' },
  ],
}

export class MockStreams {
  private subs = new Set<Sub>()
  private seq = 4200
  private started = new Set<string>()
  private timers: ReturnType<typeof setTimeout>[] = []
  private ping: ReturnType<typeof setInterval> | null = null

  constructor(private server: MockServer) {}

  open(path: string, opts: StreamOptions): StreamHandle {
    const sub: Sub = { path, opts }
    this.subs.add(sub)
    setTimeout(() => opts.onStatus?.('open'), 30)
    if (!this.ping) this.ping = setInterval(() => this.emitAll('ping', {}), 15_000)
    const m = path.match(/^\/calls\/([^/]+)\/stream$/)
    if (m) this.startContinuation(m[1]!)
    if (path === '/switchboard/stream') for (const l of this.server.db.switchboard.lines) this.startContinuation(l.callId)
    return { close: () => { this.subs.delete(sub) } }
  }

  private deliver(sub: Sub, type: string, callId: string | null, data: unknown) {
    const env = { type, at: this.server.nowIso(), orgId: this.server.db.orgId, callId, data }
    sub.opts.onEvent({ id: String(++this.seq), event: type, data: JSON.stringify(env) })
  }

  private emitAll(type: string, data: unknown) { for (const s of this.subs) this.deliver(s, type, null, data) }
  emitOrg(type: string, data: unknown, callId: string | null = null) {
    for (const s of this.subs) if (s.path === '/switchboard/stream') this.deliver(s, type, callId, data)
  }

  emitCall(callId: string, type: string, data: unknown) {
    for (const s of this.subs) if (s.path === `/calls/${callId}/stream`) this.deliver(s, type, callId, data)
  }

  private later(ms: number, fn: () => void) { this.timers.push(setTimeout(fn, ms)) }

  private nextTurn(call: CallDetail, speaker: Turn['speaker'], text: string, label?: string, textEn?: string | null): Turn {
    const t = this.server.db.transcripts[call.id]
    const last = t?.turns[t.turns.length - 1]
    const atMs = Math.max((last?.endMs ?? 0) + 800, Date.parse(this.server.nowIso()) - Date.parse(call.startedAt))
    const turn: Turn = {
      id: `mock-turn-${call.id.slice(-4)}-${++this.seq}`,
      seq: (last?.seq ?? 0) + 1,
      speaker,
      speakerLabel: label ?? (speaker === 'line' ? 'ClaimVoice' : speaker === 'caller' ? call.callerLabel : 'Larkspur'),
      text,
      textEn: textEn ?? null,
      language: speaker === 'whisper' || speaker === 'person' ? 'en' : call.language,
      atMs,
      endMs: atMs + Math.max(1200, text.split(/\s+/).length * 380),
      stage: call.stage.key,
      confidence: speaker === 'caller' ? 0.92 : null,
      interrupted: false,
      redactions: 0,
      flags: [],
    }
    this.server.appendTurn(call.id, turn)
    return turn
  }

  /** Speak a caller turn word by word (turn.partial) then finalise it (turn.final). */
  private speakCaller(call: CallDetail, text: string, done: (t: Turn) => void) {
    const words = text.split(/\s+/)
    words.forEach((_, i) => this.later(i * 260, () => this.emitCall(call.id, 'turn.partial', { speaker: 'caller', text: words.slice(0, i + 1).join(' ') })))
    this.later(words.length * 260 + 500, () => {
      const turn = this.nextTurn(call, 'caller', text)
      this.emitCall(call.id, 'turn.final', turn)
      done(turn)
    })
  }

  private startContinuation(callId: string) {
    if (this.started.has(callId)) return
    const line = this.server.findLine(callId)
    const call = this.server.db.calls[callId]
    if (!line || !call) return
    const steps = CONTINUATIONS[line.lineLabel]
    if (!steps) return
    this.started.add(callId)
    let at = 0
    for (const step of steps) {
      at += step.delay
      this.later(at, () => this.runStep(call, line, step))
    }
  }

  private runStep(call: CallDetail, line: LiveLine, step: Step) {
    if (call.listeners.some(l => l.mode === 'took_over')) return
    const after = (turn: Turn) => {
      if (step.stage) {
        call.stage = { ...call.stage, ...step.stage } as StageInfo
        line.stage = call.stage
        this.emitCall(call.id, 'stage.changed', call.stage)
      }
      for (const s of step.slots ?? []) this.updateSlot(call, s, turn)
      if (step.heard) line.heard = [{ key: step.heard.key, text: step.heard.text, tone: 'normal' as const }, ...line.heard.filter(h => h.key !== step.heard!.key)].slice(0, 4)
      if (step.asked) line.lastAsked = { text: step.asked, textEn: null }
      this.emitOrg('line.updated', line, call.id)
    }
    if (step.speaker === 'caller') this.speakCaller(call, step.text, after)
    else {
      const turn = this.nextTurn(call, 'line', step.text)
      this.emitCall(call.id, 'turn.final', turn)
      after(turn)
    }
  }

  private updateSlot(call: CallDetail, partial: Partial<Slot>, turn: Turn) {
    const file = this.server.db.claimFiles[call.id]
    if (!file) return
    const secs = Math.floor(turn.atMs / 1000)
    let slot: Slot | undefined
    for (const sec of file.sections) slot = slot ?? sec.slots.find(s => s.key === partial.key)
    const phrase = partial.display ?? ''
    const start = Math.max(0, turn.text.indexOf(phrase.split(',')[0]!.split(' ')[0]!))
    const base: Slot = slot ?? {
      key: partial.key!, label: partial.label ?? partial.key!, value: null, display: '', confidence: null, confidenceLabel: null,
      source: 'heard', sourceLabel: '', span: null, heardAtSeconds: null, changedAtSeconds: null, confirmed: false, required: false, history: [],
    }
    Object.assign(base, partial, {
      value: partial.display, source: 'heard', confidence: 0.9, confidenceLabel: 'sure',
      sourceLabel: `▸ ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`,
      span: { turnId: turn.id, start, end: Math.min(turn.text.length, start + Math.max(4, Math.min(turn.text.length, 28))) },
      heardAtSeconds: secs,
    })
    if (!slot) (file.sections.find(s => s.key === 'details') ?? file.sections[file.sections.length - 1])?.slots.push(base)
    file.progress = Math.min(1, file.progress + 0.06)
    this.emitCall(call.id, 'slot.updated', { slot: base, progress: file.progress })
  }

  whisper(call: CallDetail, text: string) {
    const p = this.server.person()
    const first = p?.fullName.split(' ')[0] ?? 'Renée'
    const turn = this.nextTurn(call, 'whisper', text, `Whisper, ClaimVoice only · ${first}`)
    this.emitCall(call.id, 'whisper.sent', { id: turn.id, text, by: p?.fullName ?? '', at: this.server.nowIso() })
    this.emitCall(call.id, 'turn.final', turn)
    this.later(3500, () => {
      if (call.listeners.some(l => l.mode === 'took_over')) return
      const q = text.replace(/^ask (if|whether)\s+/i, '').replace(/\.$/, '')
      const say = call.language === 'fr'
        ? `Une petite question de plus : ${q.charAt(0).toLowerCase()}${q.slice(1)}?`
        : `One more thing before we go on: ${/^ask/i.test(text) ? `is ${q.replace(/\bis\b\s*/i, '')}` : q.charAt(0).toLowerCase() + q.slice(1)}?`
      const t2 = this.nextTurn(call, 'line', say)
      this.emitCall(call.id, 'turn.final', t2)
    })
    return { id: turn.id, at: this.server.nowIso() }
  }

  takeover(call: CallDetail) {
    const p = this.server.person()
    const t = this.nextTurn(call, 'system', `${p?.fullName ?? 'A person'} joined the call. ClaimVoice is taking notes.`, 'ClaimVoice notes')
    this.emitCall(call.id, 'turn.final', t)
    this.emitCall(call.id, 'notice', { kind: 'person_joined', text: t.text })
  }

  giveBack(call: CallDetail) {
    const t = this.nextTurn(call, 'line', call.language === 'fr' ? 'Me revoici. On continue là où on était.' : 'I\'m back with you. Let\'s carry on where we were.')
    this.emitCall(call.id, 'turn.final', t)
  }

  say(call: CallDetail, text: string) {
    const p = this.server.person()
    const t = this.nextTurn(call, 'person', text, p?.fullName ?? 'Larkspur')
    this.emitCall(call.id, 'turn.final', t)
    this.later(2600, () => {
      const reply = this.nextTurn(call, 'caller', call.language === 'fr' ? 'D\'accord, merci.' : 'Okay, thanks. That helps.')
      this.emitCall(call.id, 'turn.final', reply)
    })
    return { turnId: t.id }
  }

  handoff(call: CallDetail, reason: string, team: HandoffInfo['team']): HandoffInfo {
    const db = this.server.db
    const line = db.liveLines[call.id]
    const h: HandoffInfo = {
      id: `mock-handoff-${++this.seq}`, callId: call.id, reason: 'supervisor', reasonLabel: 'Passed on by a supervisor', detail: reason,
      priority: 'normal', state: 'waiting', requestedAt: this.server.nowIso(), waitingSeconds: 0, acceptedBy: null, acceptedAt: null,
      callerLabel: call.callerLabel, lineLabel: line?.lineLabel ?? 'Line', place: line?.place ?? null, lossTypeLabel: call.lossTypeLabel,
      language: call.language, summary: call.summary ?? reason, actionsTaken: [], to: null, team: team ?? 'intake',
    }
    db.switchboard.handoffTray.push(h)
    db.switchboard.lines = db.switchboard.lines.filter(l => l.callId !== call.id)
    if (line) { line.state = 'waiting_for_person'; line.stateLabel = 'Waiting for a person'; line.handoff = h }
    this.emitOrg('handoff.requested', h, call.id)
    return h
  }

  startDemoCall(body: Record<string, unknown>) {
    const id = `demo-${Date.now().toString(36)}`
    const lang = body.language === 'fr' ? 'fr' : 'en'
    const now = this.server.nowIso()
    const stage = stageFor(1, 'greeting', 'Greeting')
    const call: CallDetail = {
      id, reference: 'CALL-260108-DEMO', startedAt: now, endedAt: null, durationSeconds: null, state: 'ringing', stateLabel: 'Ringing',
      mode: (body.mode as CallDetail['mode']) ?? 'browser_speech', language: lang, callerLabel: 'Unverified caller', regionLabel: 'Alberta',
      lossTypeLabel: null, outcome: 'in_progress', outcomeLabel: 'In progress', claimId: null, claimNumber: null, flags: [], qaScore: null,
      isSample: true, stage, stages: [], consent: { rule: 'one_party', ruleLabel: 'One-party consent (Alberta)', region: 'CA-AB', answer: 'pending', answerLabel: 'Waiting for consent', recording: false, askedAt: null, turnId: null },
      policyId: null, policyNumber: null, holderId: null, handoff: null, listeners: [], summary: null, summaryEn: null, recordingAvailable: false, surgeId: null,
      lineLabel: 'Line 6', place: null,
    }
    return {
      call,
      connect: { callId: id, callerToken: 'mock-token', offerUrl: `/api/v1/calls/${id}/webrtc/offer`, iceUrl: `/api/v1/calls/${id}/webrtc/ice`, websocketUrl: '', dataChannelLabel: 'claimvoice', iceServers: [], maxSeconds: 360 },
    }
  }
}
