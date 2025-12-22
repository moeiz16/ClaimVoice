import { describe, expect, it } from 'vitest'
import { alignSlip, builtInCall, horizonBars, normaliseSlip, parseLandingCall, reasonText, slipAt } from '../app/utils/landingCall'
import { looksLikeCardNumber } from '../app/mock/demoLine'

describe('the landing call', () => {
  it('ships an English and a French script with the same shape', () => {
    const en = builtInCall('en')
    const fr = builtInCall('fr')
    expect(en.turns).toHaveLength(fr.turns.length)
    expect(en.durationSeconds).toBe(76)
    expect(en.turns.some(t => t.hush != null)).toBe(true)
    expect(en.turns.map(t => t.text).join(' ')).toMatch(/wind/i)
    expect(en.turns.map(t => t.text).join(' ')).not.toMatch(/hail/i)
  })

  it('keeps every heard span inside its turn', () => {
    for (const lang of ['en', 'fr'] as const) {
      for (const t of builtInCall(lang).turns) for (const s of t.spans ?? []) expect(t.text).toContain(s.text)
    }
  })

  it('accepts the timed transcript file and rejects broken ones', () => {
    expect(parseLandingCall(null)).toBeNull()
    expect(parseLandingCall({ durationSeconds: 10, turns: [] })).toBeNull()
    expect(parseLandingCall({ durationSeconds: 10, turns: [{ who: 'robot', from: 0, to: 1, text: 'x' }] })).toBeNull()
    const ok = parseLandingCall({ durationSeconds: 9, turns: [{ who: 'cv', from: 0, to: 4, text: 'Hello there' }] })
    expect(ok?.durationSeconds).toBe(9)
    expect(ok?.slip.length).toBeGreaterThan(0)
  })

  it('shows the latest value of each slip field, in first-heard order', () => {
    const slip = builtInCall('en').slip
    const at31 = slipAt(slip, 31)
    expect(at31.find(s => s.key === 'skylight')?.label).toBe('Kitchen skylight smashed, now covered')
    expect(at31[0]!.key).toBe('consent')
    expect(slipAt(slip, 0)).toEqual([])
  })

  it('moves "from the policy" out of labels and lands values when their words are said', () => {
    expect(normaliseSlip({ key: 'where', label: '1418 Elbow Drive SW, from the policy', at: 13 })).toEqual({ key: 'where', label: '1418 Elbow Drive SW', at: 13, fromPolicy: true })
    const aligned = alignSlip([{ who: 'caller', from: 10, to: 14, text: 'one two three four', spans: [{ text: 'three four', key: 'policy' }] }], [{ key: 'policy', label: 'P', at: 10 }])
    expect(aligned[0]!.at).toBeCloseTo(13.5)
  })

  it('draws the horizon from peaks when present, with the hush blanked', () => {
    const call = { ...builtInCall('en'), durationSeconds: 10, turns: [{ who: 'caller' as const, from: 0, to: 10, text: 'x', hush: 5 }], peaks: { cv: [0, 0, 0, 0], caller: [0.5, 0.5, 0.5, 0.5] } }
    const bars = horizonBars(call, 10)
    expect(bars[1]!.who).toBe('caller')
    expect(bars[8]!.who).toBe('hush')
    expect(horizonBars(builtInCall('en'), 50)).toHaveLength(50)
  })

  it('reads route reasons as plain strings or objects', () => {
    expect(reasonText('Nobody hurt')).toBe('Nobody hurt')
    expect(reasonText({ text: 'Nothing open to the weather', atSeconds: 38 })).toBe('Nothing open to the weather')
  })
})

describe('the demo line spots card numbers', () => {
  it('catches spoken or typed digits after a card is mentioned', () => {
    expect(looksLikeCardNumber('Do you want my Visa? It\'s four five one two')).toBe(true)
    expect(looksLikeCardNumber('my card is 4512 0000')).toBe(true)
    expect(looksLikeCardNumber('My policy is LM-AB-204118')).toBe(false)
  })
})
