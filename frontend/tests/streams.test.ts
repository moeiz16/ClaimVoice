import { describe, expect, it } from 'vitest'
import { SseParser } from '../app/utils/sse'
import { applyCallEvent, applySwitchboardEvent, parseEnvelope, waitingCount, type CallState } from '../app/utils/events'
import type { ClaimSummary, HandoffInfo, LiveLine, Slot, SwitchboardSnapshot, Turn } from '../app/types/api'

describe('SSE framing', () => {
  it('parses id, event and data, and remembers the retry and last id', () => {
    const p = new SseParser()
    const out = p.feed('retry: 3000\n\nid: 7\nevent: line.updated\ndata: {"a":1}\n\n')
    expect(p.retry).toBe(3000)
    expect(out).toEqual([{ id: '7', event: 'line.updated', data: '{"a":1}' }])
    expect(p.lastEventId).toBe('7')
  })

  it('handles events split across chunks, CRLF, comments and multi-line data', () => {
    const p = new SseParser()
    expect(p.feed(': keep-alive\r\nevent: ping\r\nda')).toEqual([])
    expect(p.feed('ta: one\r\ndata: two\r\n\r\n')).toEqual([{ id: null, event: 'ping', data: 'one\ntwo' }])
  })

  it('defaults the event name to message', () => {
    expect(new SseParser().feed('data: x\n\n')[0]!.event).toBe('message')
  })

  it('rejects envelopes that are not JSON objects with a type', () => {
    expect(parseEnvelope('not json')).toBeNull()
    expect(parseEnvelope('{"type":"ping","data":{}}')?.type).toBe('ping')
  })
})

const stage = { key: 'loss_details', label: 'Details', step: 4, stepLabel: 'What happened', steps: 7, nextLabel: 'Photos next' }
function line(n: number, over: Partial<LiveLine> = {}): LiveLine {
  return {
    callId: `call-${n}`, lineLabel: `Line ${n}`, state: 'with_line', stateLabel: 'With ClaimVoice', stage, mode: 'browser_speech', language: 'en',
    callerLabel: `Caller ${n}`, callerVerified: true, callerPhoneMasked: null, region: 'CA-AB', regionLabel: 'Alberta', lossType: 'wind', lossTypeLabel: 'Wind',
    answeredAt: '2026-01-08T14:39:00Z', flags: [], mood: { key: 'calm', label: 'Sounds calm', detail: null }, handoff: null, listeners: [], inSurge: true,
    lastAsked: null, place: 'Calgary', heard: [], claimFileProgress: 0.4, isSample: true, ...over,
  }
}
function handoff(id: string, priority: HandoffInfo['priority'], requestedAt: string, state: HandoffInfo['state'] = 'waiting'): HandoffInfo {
  return {
    id, callId: `call-${id}`, reason: priority === 'urgent' ? 'urgent_safety' : 'caller_asked', reasonLabel: '', detail: '', priority, state, requestedAt,
    waitingSeconds: 0, acceptedBy: null, acceptedAt: null, callerLabel: '', lineLabel: '', place: null, lossTypeLabel: null, language: 'en', summary: '',
    actionsTaken: [], to: null, team: null,
  }
}
const snap = (over: Partial<SwitchboardSnapshot> = {}): SwitchboardSnapshot => ({
  lines: [line(1), line(2)], handoffTray: [], surge: null, recentClaims: [], freePeople: [], caption: '',
  today: { callsAnswered: 0, answeredFirstRingShare: 1, medianHandleSeconds: 0, handoffs: 0, claimsCreated: 0, averageQaScore: null, surgeCalls: 0 }, lastEventId: 1, ...over,
})

describe('the line desk stream', () => {
  it('adds new lines in line order and updates existing ones in place', () => {
    const s = applySwitchboardEvent(snap(), 'line.opened', line(10)) as SwitchboardSnapshot
    expect(s.lines.map(l => l.lineLabel)).toEqual(['Line 1', 'Line 2', 'Line 10'])
    const u = applySwitchboardEvent(s, 'line.updated', line(2, { mood: { key: 'shaken', label: 'Sounds shaken', detail: null } })) as SwitchboardSnapshot
    expect(u.lines.find(l => l.callId === 'call-2')!.mood.label).toBe('Sounds shaken')
  })

  it('moves a line waiting for a person into the tray, urgent first', () => {
    const tray = [handoff('a', 'normal', '2026-01-08T14:30:00Z')]
    const urgent = line(2, { state: 'waiting_for_person', handoff: { ...handoff('b', 'urgent', '2026-01-08T14:40:00Z'), callId: 'call-2' } })
    const s = applySwitchboardEvent(snap({ handoffTray: tray }), 'line.updated', urgent) as SwitchboardSnapshot
    expect(s.lines.map(l => l.callId)).toEqual(['call-1'])
    expect(s.handoffTray.map(h => h.id)).toEqual(['b', 'a'])
    expect(waitingCount(s)).toBe(2)
  })

  it('removes a hand-off once someone takes it', () => {
    const s = applySwitchboardEvent(snap({ handoffTray: [handoff('a', 'normal', '2026-01-08T14:30:00Z')] }), 'handoff.updated', handoff('a', 'normal', '2026-01-08T14:30:00Z', 'accepted')) as SwitchboardSnapshot
    expect(s.handoffTray).toEqual([])
  })

  it('closes lines, keeps at most eight finished claims, and asks for a reload on resync', () => {
    const closed = applySwitchboardEvent(snap(), 'line.closed', { callId: 'call-1' }) as SwitchboardSnapshot
    expect(closed.lines.map(l => l.callId)).toEqual(['call-2'])
    const claim = (id: string) => ({ id }) as ClaimSummary
    let s = snap({ recentClaims: Array.from({ length: 8 }, (_, i) => claim(`c${i}`)) })
    s = applySwitchboardEvent(s, 'claim.created', claim('new')) as SwitchboardSnapshot
    expect(s.recentClaims).toHaveLength(8)
    expect(s.recentClaims[0]!.id).toBe('new')
    expect(applySwitchboardEvent(s, 'claim.routed', claim('unknown'))).toBe(s)
    expect(applySwitchboardEvent(s, 'resync', {})).toBe('resync')
  })
})

describe('one call\'s stream', () => {
  const turn = (id: string, speaker: Turn['speaker'] = 'caller'): Turn => ({ id, seq: 1, speaker, speakerLabel: '', text: 'hi', language: 'en', atMs: 0, endMs: 1, stage: '', confidence: null, interrupted: false, redactions: 0, flags: [] })
  const slot = (key: string, display: string): Slot => ({ key, label: key, value: display, display, confidence: 1, confidenceLabel: 'sure', source: 'heard', sourceLabel: '▸ 0:10', span: null, heardAtSeconds: 10, changedAtSeconds: null, confirmed: false, required: false, history: [] })
  const base = (): CallState => ({
    call: null, turns: [], partial: 'hel', ended: null, notices: [],
    file: { callId: 'c', claimId: null, lossType: null, lossTypeLabel: null, progress: 0, missing: [], sections: [{ key: 'policy', label: 'Policy', slots: [slot('policy', 'old')] }, { key: 'details', label: 'Details', slots: [] }] },
  })

  it('appends final turns once and clears the live caption', () => {
    let s = applyCallEvent(base(), 'turn.final', turn('t1'))
    s = applyCallEvent(s, 'turn.final', turn('t1'))
    expect(s.turns).toHaveLength(1)
    expect(s.partial).toBe('')
    expect(applyCallEvent(base(), 'turn.partial', { speaker: 'caller', text: 'hello th' }).partial).toBe('hello th')
  })

  it('updates a heard value in place, or adds it to the details', () => {
    let s = applyCallEvent(base(), 'slot.updated', { slot: slot('policy', 'LM-AB-204118'), progress: 0.3 })
    expect(s.file!.sections[0]!.slots[0]!.display).toBe('LM-AB-204118')
    expect(s.file!.progress).toBe(0.3)
    s = applyCallEvent(s, 'slot.updated', { slot: slot('siding', 'North wall'), progress: 0.4 })
    expect(s.file!.sections[1]!.slots.map(x => x.key)).toEqual(['siding'])
  })

  it('records the end of the call and keeps the last notices', () => {
    let s = base()
    for (let i = 0; i < 7; i++) s = applyCallEvent(s, 'notice', { kind: 'k', text: String(i) })
    expect(s.notices.map(n => n.text)).toEqual(['2', '3', '4', '5', '6'])
    s = applyCallEvent(s, 'call.ended', { reason: 'completed', claimId: 'cl', claimNumber: 'CV-26-01870' })
    expect(s.ended?.claimNumber).toBe('CV-26-01870')
  })
})
