// Build transcript marks from a claim file: every heard value points at its words (Slot.span), keyed by slot key.
import type { ClaimFile, Slot } from '~/types/api'
import type { Mark } from './transcript'

export function marksByTurn(file: ClaimFile | null | undefined, extra: { turnId: string, start: number, end: number, key: string, kind?: 'heard' | 'sign' }[] = []): Record<string, Mark[]> {
  const out: Record<string, Mark[]> = {}
  const add = (turnId: string, m: Mark) => { (out[turnId] ??= []).push(m) }
  for (const sec of file?.sections ?? []) {
    for (const s of sec.slots) if (s.span) add(s.span.turnId, { start: s.span.start, end: s.span.end, key: s.key })
  }
  for (const e of extra) add(e.turnId, { start: e.start, end: e.end, key: e.key, kind: e.kind ?? 'heard' })
  return out
}

/** The slot whose span this mark key belongs to. */
export function slotByKey(file: ClaimFile | null | undefined, key: string): Slot | null {
  for (const sec of file?.sections ?? []) for (const s of sec.slots) if (s.key === key) return s
  return null
}

/** Section completeness: true when every required slot has a value. */
export function sectionDone(slots: Slot[]): boolean {
  const req = slots.filter(s => s.required)
  return req.length > 0 && req.every(s => !!s.display)
}
