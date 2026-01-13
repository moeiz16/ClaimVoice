import { describe, expect, it } from 'vitest'
import type { ClaimFile, Slot } from '../app/types/api'
import { boxWidth, buildNotice, marginNote, slotsDone, STEPS, stepperIndex } from '../app/utils/notice'

const slot = (key: string, display: string, over: Partial<Slot> = {}): Slot => ({
  key, label: key, value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: 'heard', sourceLabel: '▸ 0:10',
  span: null, heardAtSeconds: 10, changedAtSeconds: null, confirmed: true, required: true, history: [], ...over,
})
const file = (sections: ClaimFile['sections']): ClaimFile => ({ callId: 'c1', claimId: null, lossType: 'wind', lossTypeLabel: 'Wind', progress: 0.5, missing: [], sections })

describe('the loss notice', () => {
  it('numbers sections by the script step that fills them, joining caller and policy, loss and details', () => {
    const n = buildNotice(file([
      { key: 'caller', label: 'Caller', slots: [slot('name', 'Gord')] },
      { key: 'policy', label: 'Policy', slots: [slot('policy', 'LM-AB-1')] },
      { key: 'loss', label: 'What happened', slots: [slot('what', 'Wind')] },
      { key: 'details', label: 'Damage', slots: [slot('roof', '')] },
      { key: 'photos', label: 'Photos', slots: [] },
      { key: 'next_steps', label: 'Next steps', slots: [slot('read', '', { required: false })] },
    ]), 4)
    expect(n.map(s => s.step)).toEqual([2, 4, 7])
    expect(n[0]!.title).toBe('Caller · Policy')
    expect(n[0]!.state).toBe('done')
    expect(n[1]!.state).toBe('current')
    expect(n[2]!.state).toBe('waiting')
  })

  it('marks reached but unfinished sections open, and every unfinished section open once the call ends', () => {
    const f = file([{ key: 'safety', label: 'Safety', slots: [slot('hurt', '')] }, { key: 'coverage', label: 'Coverage', slots: [slot('c', '')] }])
    expect(buildNotice(f, 5).map(s => s.state)).toEqual(['open', 'waiting'])
    expect(buildNotice(f, 5, true).map(s => s.state)).toEqual(['open', 'open'])
    expect(buildNotice(null, 1)).toEqual([])
  })

  it('counts a section done when its required values are filled, or all of them when none is required', () => {
    expect(slotsDone([slot('a', 'x'), slot('b', '', { required: false })])).toBe(true)
    expect(slotsDone([slot('a', '', { required: false }), slot('b', 'y', { required: false })])).toBe(false)
    expect(slotsDone([])).toBe(false)
  })

  it('maps the stage step to the stepper and runs past the end when the call is over', () => {
    expect(STEPS).toHaveLength(7)
    expect(stepperIndex(4, false)).toBe(3)
    expect(stepperIndex(0, false)).toBe(0)
    expect(stepperIndex(9, false)).toBe(6)
    expect(stepperIndex(3, true)).toBe(7)
  })

  it('widens boxes for long values', () => {
    expect(boxWidth(slot('a', 'Wind'))).toBe(1)
    expect(boxWidth(slot('a', 'Kitchen skylight smashed by debris'))).toBe(2)
    expect(boxWidth(slot('a', 'x'.repeat(80)))).toBe(4)
  })

  it('quotes the caller\'s words around a heard value as a margin note, trimmed with ellipses', () => {
    const turns = [{ id: 't1', text: 'Oh, and the skylight in the kitchen got smashed by something blown off the neighbour\'s deck.' }]
    const start = turns[0]!.text.indexOf('skylight')
    expect(marginNote(turns, { turnId: 't1', start, end: start + 8 }, 5)).toBe('… and the skylight in the …')
    expect(marginNote(turns, { turnId: 't1', start: 0, end: turns[0]!.text.length }, 40)).toBe(turns[0]!.text)
  })

  it('never quotes a card-number moment, and says nothing when the words are missing', () => {
    const turns = [{ id: 't1', text: 'It\'s four five [card number removed] okay' }]
    const s = turns[0]!.text.indexOf('[card')
    expect(marginNote(turns, { turnId: 't1', start: s, end: s + 21 })).toBeNull()
    expect(marginNote(turns, { turnId: 'nope', start: 0, end: 3 })).toBeNull()
    expect(marginNote(null, { turnId: 't1', start: 0, end: 3 })).toBeNull()
    expect(marginNote(turns, null)).toBeNull()
  })
})
