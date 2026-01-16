// The answer sheet (DESIGN.md §3): the claim file grouped by the script step that asks for it, so each group is one
// question ClaimVoice asked and its answers. Each value keeps its source.
import type { ClaimFile, ClaimFileSection, SectionKey, Slot } from '~/types/api'

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

/** An answer is wide (two columns) when its value or label is long; long free text gets the full row. */
export function boxWidth(slot: Slot): 1 | 2 | 4 {
  const len = (slot.display ?? '').length
  if (len > 64) return 4
  if (len > 26 || slot.label.length > 22) return 2
  return 1
}
