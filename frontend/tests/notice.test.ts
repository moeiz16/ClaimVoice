import { describe, expect, it } from 'vitest'
import type { ClaimFile, Slot } from '../app/types/api'
import { boxWidth, buildNotice, slotsDone } from '../app/utils/notice'

const slot = (key: string, display: string, over: Partial<Slot> = {}): Slot => ({
  key, label: key, value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: 'heard', sourceLabel: '▸ 0:10',
  span: null, heardAtSeconds: 10, changedAtSeconds: null, confirmed: true, required: true, history: [], ...over,
})
const file = (sections: ClaimFile['sections']): ClaimFile => ({ callId: 'c1', claimId: null, lossType: 'wind', lossTypeLabel: 'Wind', progress: 0.5, missing: [], sections })

describe('the answer sheet', () => {
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

  it('widens answers for long values', () => {
    expect(boxWidth(slot('a', 'Wind'))).toBe(1)
    expect(boxWidth(slot('a', 'Kitchen skylight smashed by debris'))).toBe(2)
    expect(boxWidth(slot('a', 'x'.repeat(80)))).toBe(4)
  })
})
