// Pure reducers for the live streams (contract §1.8). The composables feed them parsed envelopes; tests feed them
// fixtures. They never mutate their input.
import type {
  CallDetail, ClaimFile, ClaimSummary, Envelope, Flag, HandoffInfo, LineClosed, LiveLine, Listener, Slot, StageInfo,
  Surge, SwitchboardSnapshot, TodayStats, Turn,
} from '~/types/api'

export function parseEnvelope(data: string): Envelope | null {
  try {
    const env = JSON.parse(data) as Envelope
    return env && typeof env === 'object' && 'type' in env ? env : null
  }
  catch {
    return null
  }
}

const byLine = (a: LiveLine, b: LiveLine) => a.lineLabel.localeCompare(b.lineLabel, undefined, { numeric: true })
const trayOrder = (a: HandoffInfo, b: HandoffInfo) => {
  const pr = { urgent: 0, high: 1, normal: 2 }
  return pr[a.priority] - pr[b.priority] || a.requestedAt.localeCompare(b.requestedAt)
}

/** Apply one org-stream event to the line desk snapshot. Returns 'resync' when the snapshot must be reloaded. */
export function applySwitchboardEvent(s: SwitchboardSnapshot, type: string, data: unknown): SwitchboardSnapshot | 'resync' {
  switch (type) {
    case 'line.opened':
    case 'line.updated': {
      const line = data as LiveLine
      const waiting = line.state === 'waiting_for_person'
      const others = s.lines.filter(l => l.callId !== line.callId)
      const lines = waiting || line.state === 'ended' ? others : [...others, line].sort(byLine)
      let tray = s.handoffTray
      if (line.handoff && waiting) tray = upsert(tray, line.handoff).sort(trayOrder)
      else tray = tray.filter(h => h.callId !== line.callId || h.state === 'waiting')
      return { ...s, lines, handoffTray: tray }
    }
    case 'line.closed': {
      const c = data as LineClosed
      return { ...s, lines: s.lines.filter(l => l.callId !== c.callId), handoffTray: s.handoffTray.filter(h => h.callId !== c.callId) }
    }
    case 'handoff.requested':
    case 'handoff.updated': {
      const h = data as HandoffInfo
      const tray = h.state === 'waiting' ? upsert(s.handoffTray, h).sort(trayOrder) : s.handoffTray.filter(x => x.id !== h.id)
      const lines = h.state === 'waiting' ? s.lines.filter(l => l.callId !== h.callId) : s.lines
      return { ...s, handoffTray: tray, lines }
    }
    case 'surge.started':
    case 'surge.updated':
      return { ...s, surge: data as Surge }
    case 'surge.ended':
      return { ...s, surge: null }
    case 'claim.created':
    case 'claim.routed':
    case 'claim.updated': {
      const c = data as ClaimSummary
      const exists = s.recentClaims.some(x => x.id === c.id)
      if (!exists && type !== 'claim.created') return s
      const recent = exists ? s.recentClaims.map(x => (x.id === c.id ? c : x)) : [c, ...s.recentClaims].slice(0, 8)
      return { ...s, recentClaims: recent }
    }
    case 'stats.updated':
      return { ...s, today: data as TodayStats }
    case 'resync':
      return 'resync'
    default:
      return s
  }
}

function upsert(list: HandoffInfo[], h: HandoffInfo): HandoffInfo[] {
  return list.some(x => x.id === h.id) ? list.map(x => (x.id === h.id ? h : x)) : [...list, h]
}

export interface CallState {
  call: CallDetail | null
  turns: Turn[]
  file: ClaimFile | null
  partial: string
  ended: { reason: string, claimId: string | null, claimNumber: string | null } | null
  notices: { kind: string, text: string }[]
}

/** Apply one per-call event. */
export function applyCallEvent(s: CallState, type: string, data: unknown): CallState {
  switch (type) {
    case 'turn.partial':
      return { ...s, partial: (data as { text: string }).text }
    case 'turn.final': {
      const t = data as Turn
      const turns = s.turns.some(x => x.id === t.id) ? s.turns.map(x => (x.id === t.id ? t : x)) : [...s.turns, t]
      return { ...s, turns, partial: t.speaker === 'caller' ? '' : s.partial }
    }
    case 'slot.updated': {
      if (!s.file) return s
      const { slot, progress } = data as { slot: Slot, progress: number }
      let placed = false
      const sections = s.file.sections.map((sec) => {
        if (!sec.slots.some(x => x.key === slot.key)) return sec
        placed = true
        return { ...sec, slots: sec.slots.map(x => (x.key === slot.key ? slot : x)) }
      })
      if (!placed && sections.length) {
        const i = Math.max(0, sections.findIndex(x => x.key === 'details'))
        sections[i] = { ...sections[i]!, slots: [...sections[i]!.slots, slot] }
      }
      return { ...s, file: { ...s.file, sections, progress } }
    }
    case 'whisper.sent': {
      // A typed note to ClaimVoice: shown as a staff-only row; the caller never hears it.
      const w = data as { id: string, text: string, by: string, at: string }
      if (s.turns.some(t => t.id === w.id)) return s
      const start = s.call ? Date.parse(s.call.startedAt) : Number.NaN
      const atMs = Number.isNaN(start) ? (s.turns[s.turns.length - 1]?.endMs ?? 0) : Math.max(0, Date.parse(w.at) - start)
      const first = (w.by ?? '').split(' ')[0] ?? ''
      const row: Turn = {
        id: w.id, seq: (s.turns[s.turns.length - 1]?.seq ?? 0) + 1, speaker: 'whisper', speakerLabel: `Whisper, ClaimVoice only${first ? ` · ${first}` : ''}`,
        text: w.text, language: 'en', atMs, endMs: atMs, stage: s.call?.stage.key ?? '', confidence: null, interrupted: false, redactions: 0, flags: [],
      }
      return { ...s, turns: [...s.turns, row] }
    }
    case 'stage.changed':
      return s.call ? { ...s, call: { ...s.call, stage: data as StageInfo } } : s
    case 'flag.raised':
      return s.call ? { ...s, call: { ...s.call, flags: [...s.call.flags, data as Flag] } } : s
    case 'handoff.updated':
      return s.call ? { ...s, call: { ...s.call, handoff: data as HandoffInfo } } : s
    case 'listener.changed':
      return s.call ? { ...s, call: { ...s.call, listeners: (data as { listeners: Listener[] }).listeners } } : s
    case 'notice':
      return { ...s, notices: [...s.notices, data as { kind: string, text: string }].slice(-5) }
    case 'call.ended': {
      const e = data as { reason: string, claimId: string | null, claimNumber: string | null }
      return { ...s, ended: e, partial: '', call: s.call ? { ...s.call, state: 'ended', claimId: e.claimId, claimNumber: e.claimNumber } : s.call }
    }
    default:
      return s
  }
}

/** Count of lines waiting for a person (the dock's Lines badge). */
export function waitingCount(s: SwitchboardSnapshot | null): number {
  return s ? s.handoffTray.filter(h => h.state === 'waiting').length : 0
}
