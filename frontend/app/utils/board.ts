// The screener's board (DESIGN.md §0.2): every live line and every caller waiting for a person as one row, in NEXT
// order, the way a broadcast screener's NEXT key takes calls: urgent safety first, then whoever has waited longest
// for a person, then people already on a call, then the lines ClaimVoice is handling (by line number), then ringing.
// The same rows drive the key bank's line keys.
import type { HandoffInfo, Iso, Lang, LiveLine } from '~/types/api'

/** The lamp on a line key. Never shown by colour alone: every lamp has a glyph and a word. */
export type Lamp = 'urgent' | 'waiting' | 'person' | 'line' | 'ringing'

export interface BoardRow {
  /** Stable key: the call id. */
  id: string
  callId: string
  lineNo: number | null
  lineLabel: string
  lamp: Lamp
  /** The state in words ("Urgent safety", "Asked for a person", "Jamal has it", "ClaimVoice on it"). */
  stateWord: string
  /** When the current state began: the hand-off request, or the answer. Timers count from here. */
  since: Iso
  callerLabel: string
  place: string | null
  lossTypeLabel: string | null
  language: Lang
  line: LiveLine | null
  handoff: HandoffInfo | null
}

export const LAMP_GLYPH: Record<Lamp, string> = {
  urgent: 'i-lucide-triangle-alert',
  waiting: 'i-lucide-hand',
  person: 'i-lucide-user-round',
  line: 'i-lucide-audio-lines',
  ringing: 'i-lucide-bell-ring',
}

/** "Line 4" → 4; anything without a number → null. */
export function lineNumber(label: string | null | undefined): number | null {
  const m = /(\d+)/.exec(label ?? '')
  return m ? Number(m[1]) : null
}

const RANK: Record<Lamp, number> = { urgent: 0, waiting: 1, person: 2, line: 3, ringing: 4 }

function personOn(line: LiveLine): string | null {
  const l = line.listeners.find(x => x.mode === 'took_over')
  return l ? l.name : null
}

function rowFromLine(line: LiveLine): BoardRow {
  const who = personOn(line)
  let lamp: Lamp = 'line'
  let stateWord = 'ClaimVoice on it'
  if (who || line.state === 'with_person') {
    lamp = 'person'
    stateWord = who ? `${who.split(' ')[0]} has it` : 'With a person'
  }
  else if (line.state === 'waiting_for_person') {
    lamp = line.flags.some(f => f.kind === 'urgent_safety') ? 'urgent' : 'waiting'
    stateWord = line.handoff?.reasonLabel ?? line.stateLabel
  }
  else if (line.state === 'ringing') {
    lamp = 'ringing'
    stateWord = line.stateLabel || 'Ringing'
  }
  return {
    id: line.callId, callId: line.callId, lineNo: lineNumber(line.lineLabel), lineLabel: line.lineLabel, lamp, stateWord,
    since: line.handoff?.requestedAt ?? line.answeredAt, callerLabel: line.callerLabel, place: line.place,
    lossTypeLabel: line.lossTypeLabel, language: line.language, line, handoff: line.handoff,
  }
}

function rowFromHandoff(h: HandoffInfo, line: LiveLine | null): BoardRow {
  return {
    id: h.callId, callId: h.callId, lineNo: lineNumber(h.lineLabel), lineLabel: h.lineLabel,
    lamp: h.priority === 'urgent' ? 'urgent' : 'waiting', stateWord: h.reasonLabel, since: h.requestedAt,
    callerLabel: h.callerLabel, place: h.place ?? line?.place ?? null, lossTypeLabel: h.lossTypeLabel ?? line?.lossTypeLabel ?? null,
    language: h.language, line, handoff: h,
  }
}

/** Every caller on the board, in NEXT order. Hand-offs still waiting take their line's row. */
export function boardRows(lines: LiveLine[], tray: HandoffInfo[]): BoardRow[] {
  const waiting = tray.filter(h => h.state === 'waiting')
  const byCall = new Map(lines.map(l => [l.callId, l]))
  const rows: BoardRow[] = waiting.map(h => rowFromHandoff(h, byCall.get(h.callId) ?? null))
  const taken = new Set(rows.map(r => r.callId))
  for (const l of lines) if (!taken.has(l.callId) && l.state !== 'ended') rows.push(rowFromLine(l))
  return rows.sort((a, b) => {
    const r = RANK[a.lamp] - RANK[b.lamp]
    if (r) return r
    // Waiting rows: longest wait first. Lines: by line number.
    if (a.lamp === 'urgent' || a.lamp === 'waiting') return a.since.localeCompare(b.since)
    return (a.lineNo ?? 99) - (b.lineNo ?? 99)
  })
}

/** The caller the NEXT key takes: the first row waiting for a person, if any. */
export function nextCaller(rows: BoardRow[]): BoardRow | null {
  return rows.find(r => r.lamp === 'urgent' || r.lamp === 'waiting') ?? null
}

/** Line keys for the key bank: by line number, so a key keeps its place while rows reorder. */
export function lineKeys(rows: BoardRow[], max = 8): BoardRow[] {
  return [...rows].sort((a, b) => (a.lineNo ?? 99) - (b.lineNo ?? 99)).slice(0, max)
}

/** A key's accessible name and tooltip, in words. */
export function keyLabel(r: BoardRow, waited: string | null): string {
  const bits = [r.lineLabel, r.callerLabel, r.stateWord.toLowerCase()]
  if (waited && (r.lamp === 'urgent' || r.lamp === 'waiting')) bits.push(`waiting ${waited}`)
  if (r.language === 'fr') bits.push('in French')
  return bits.join(' · ')
}
