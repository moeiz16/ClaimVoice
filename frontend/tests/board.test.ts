import { describe, expect, it } from 'vitest'
import type { HandoffInfo, LiveLine } from '../app/types/api'
import { boardRows, LAMP_GLYPH, lineNumber } from '../app/utils/board'

const line = (n: number, over: Partial<LiveLine> = {}): LiveLine => ({
  callId: `c${n}`, lineLabel: `Line ${n}`, state: 'with_line', stateLabel: 'With ClaimVoice', mode: 'voice', language: 'en',
  stage: { key: 'loss_details', label: 'Details', step: 4, stepLabel: 'What happened', steps: 7, nextLabel: 'Photos next' },
  callerLabel: `Caller ${n}`, callerVerified: true, callerPhoneMasked: null, region: 'CA-AB', regionLabel: 'Alberta',
  lossType: 'wind', lossTypeLabel: 'Wind', answeredAt: `2026-01-08T14:3${n}:00Z`, flags: [], mood: { key: 'calm', label: 'Sounds calm', detail: null },
  handoff: null, listeners: [], inSurge: true, lastAsked: null, place: 'Calgary', heard: [], claimFileProgress: 0.4, isSample: true, ...over,
})
const handoff = (n: number, priority: HandoffInfo['priority'], requestedAt: string, over: Partial<HandoffInfo> = {}): HandoffInfo => ({
  id: `h${n}`, callId: `c${n}`, reason: priority === 'urgent' ? 'urgent_safety' : 'caller_asked', reasonLabel: priority === 'urgent' ? 'Urgent safety' : 'Asked for a person',
  detail: 'Smells gas', priority, state: 'waiting', requestedAt, waitingSeconds: 60, acceptedBy: null, acceptedAt: null, callerLabel: `Caller ${n}`,
  lineLabel: `Line ${n}`, place: 'Airdrie', lossTypeLabel: 'Wind', language: 'en', summary: 'Summary', actionsTaken: [], to: null, team: null, ...over,
})

describe('callers on the lines', () => {
  it('reads line numbers from labels', () => {
    expect(lineNumber('Line 12')).toBe(12)
    expect(lineNumber('Ligne 3')).toBe(3)
    expect(lineNumber('Overflow')).toBeNull()
    expect(lineNumber(null)).toBeNull()
  })

  it('orders callers to take: urgent, then the longest wait, then people on calls, then the lines by number', () => {
    const lines = [line(3), line(1), line(2, { listeners: [{ userId: 'u', name: 'Jamal Haddad', mode: 'took_over' }] })]
    const tray = [handoff(5, 'normal', '2026-01-08T14:40:00Z'), handoff(4, 'urgent', '2026-01-08T14:41:00Z'), handoff(6, 'high', '2026-01-08T14:39:00Z')]
    const rows = boardRows(lines, tray)
    expect(rows.map(r => r.callId)).toEqual(['c4', 'c6', 'c5', 'c2', 'c1', 'c3'])
    expect(rows[0]!.lamp).toBe('urgent')
    expect(rows[3]!.stateWord).toBe('Jamal has it')
    expect(rows[4]!.stateWord).toBe('ClaimVoice on it')
  })

  it('gives a waiting hand-off its line\'s row instead of listing the caller twice', () => {
    const rows = boardRows([line(4, { state: 'waiting_for_person' })], [handoff(4, 'urgent', '2026-01-08T14:41:00Z')])
    expect(rows).toHaveLength(1)
    expect(rows[0]!.handoff?.id).toBe('h4')
    expect(rows[0]!.line?.callId).toBe('c4')
  })

  it('leaves out accepted hand-offs and ended lines', () => {
    const rows = boardRows([line(1, { state: 'ended' }), line(2)], [handoff(7, 'normal', '2026-01-08T14:40:00Z', { state: 'accepted' })])
    expect(rows.map(r => r.callId)).toEqual(['c2'])
  })

  it('names every state in words and gives it a glyph, so state is never colour alone', () => {
    const [urgent] = boardRows([], [handoff(4, 'urgent', '2026-01-08T14:41:00Z', { language: 'fr' })])
    expect(urgent!.stateWord).toBe('Urgent safety')
    expect(urgent!.language).toBe('fr')
    expect(Object.values(LAMP_GLYPH).every(g => g.startsWith('i-lucide-'))).toBe(true)
  })
})
