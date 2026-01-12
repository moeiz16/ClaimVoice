// The loss notice (DESIGN.md §0.2): the claim file as a boxed form whose numbered sections are the seven script
// steps, so the stepper over the tape and the form beneath it are one thing. Each box carries its label, its value
// with a source, and a margin note: the caller's own words that filled it.
import type { ClaimFile, ClaimFileSection, SectionKey, Slot, TextSpan, Turn } from '~/types/api'
import { CARD_TOKEN } from './transcript'

/** The seven script steps, in order (the stepper's items). */
export const STEPS = ['Consent', 'Policy', 'Safety', 'What happened', 'Photos', 'Coverage', 'Read-back'] as const

/** Which script step fills each claim-file section. */
export const SECTION_STEP: Record<SectionKey, number> = {
  caller: 2, policy: 2, safety: 3, loss: 4, details: 4, photos: 5, coverage: 6, next_steps: 7,
}

export type SectionState = 'done' | 'current' | 'open' | 'waiting'

export interface NoticeSection {
  step: number
  key: string
  title: string
  slots: Slot[]
  state: SectionState
}

/** True when every required slot of a set has a value (a set with no required slots is done when all are filled). */
export function slotsDone(slots: Slot[]): boolean {
  const req = slots.filter(s => s.required)
  const need = req.length ? req : slots
  return need.length > 0 && need.every(s => !!s.display)
}

/**
 * Group a claim file's sections into numbered notice sections. `step` is the call's current script step (1–7);
 * `ended` marks every reached section as done or open. Sections keep the API's own labels.
 */
export function buildNotice(file: ClaimFile | null | undefined, step: number, ended = false): NoticeSection[] {
  const groups = new Map<number, ClaimFileSection[]>()
  for (const sec of file?.sections ?? []) {
    if (!sec.slots.length) continue
    const n = SECTION_STEP[sec.key] ?? 7
    groups.set(n, [...(groups.get(n) ?? []), sec])
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0]).map(([n, secs]) => {
    const slots = secs.flatMap(s => s.slots)
    const done = slotsDone(slots)
    const any = slots.some(s => !!s.display)
    let state: SectionState
    if (done) state = 'done'
    else if (!ended && n === step) state = 'current'
    else if (any || ended || n < step) state = 'open'
    else state = 'waiting'
    return { step: n, key: secs.map(s => s.key).join('+'), title: secs.map(s => s.label).join(' · '), slots, state }
  })
}

/** Index of the stepper's active item (0-based) for a stage step; past the end when the call has ended. */
export function stepperIndex(step: number, ended: boolean): number {
  return ended ? STEPS.length : Math.min(Math.max(step, 1), STEPS.length) - 1
}

/** A box is wide (two columns) when its value or label is long; long free text gets the full row. */
export function boxWidth(slot: Slot): 1 | 2 | 4 {
  const len = (slot.display ?? '').length
  if (len > 64) return 4
  if (len > 26 || slot.label.length > 22) return 2
  return 1
}

/**
 * The margin note for a heard value: the caller's words around its span, at most `maxWords` words, with an ellipsis
 * where it was cut. Card-number moments are never quoted. Returns null when the words aren't available.
 */
export function marginNote(turns: Pick<Turn, 'id' | 'text'>[] | null | undefined, span: TextSpan | null | undefined, maxWords = 9): string | null {
  if (!span || !turns?.length) return null
  const turn = turns.find(t => t.id === span.turnId)
  if (!turn) return null
  const text = turn.text
  const start = Math.max(0, Math.min(span.start, text.length))
  const end = Math.max(start, Math.min(span.end, text.length))
  const core = text.slice(start, end).trim()
  if (!core || core.toLowerCase().includes(CARD_TOKEN)) return null
  const before = text.slice(0, start)
  const after = text.slice(end)
  const countWords = (x: string) => x.trim().split(/\s+/).filter(Boolean).length
  const room = Math.max(0, maxWords - countWords(core))
  const nb = countWords(before)
  const na = countWords(after)
  // Share the room between the words before and after, giving any unused share to the other side.
  let pre = Math.min(nb, Math.ceil(room / 2))
  const post = Math.min(na, room - pre)
  pre = Math.min(nb, room - post)
  // Cut on the original text so punctuation keeps its place ("LM-AB-204118." not "LM-AB-204118 .").
  const lead = pre ? (before.match(new RegExp(`(?:\\S+\\s*){${pre}}$`))?.[0] ?? '') : ''
  const tail = post ? (after.match(new RegExp(`^(?:\\s*\\S+){${post}}`))?.[0] ?? '') : ''
  const quote = `${lead}${text.slice(start, end)}${tail}`.replace(/\[[^\]]*\]/g, '').replace(/\s{2,}/g, ' ').trim()
  return `${pre < nb ? '… ' : ''}${quote}${post < na ? ' …' : ''}`
}
