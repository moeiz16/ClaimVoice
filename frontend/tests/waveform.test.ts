import { describe, expect, it } from 'vitest'
import {
  conversationBars, defaultRhythm, levelStep, LiveBars, rmsLevel, rng, seedOf, splitPeaks, syntheticLevel, withHushes,
} from '../app/utils/waveform'
import { layoutPins, pinWidth } from '../app/utils/pins'
import { silentWav } from '../app/utils/audio'

describe('the conversation waveform', () => {
  it('is deterministic for a seed', () => {
    const a = rng(11)
    const b = rng(11)
    expect([a(), a(), a()]).toEqual([b(), b(), b()])
    expect(seedOf('CV-26-01842')).toBe(seedOf('CV-26-01842'))
    expect(seedOf('a')).not.toBe(seedOf('b'))
  })

  it('places each speaker in their turn and leaves gaps between turns', () => {
    const bars = conversationBars([{ who: 'cv', from: 0, to: 5 }, { who: 'caller', from: 6, to: 10 }], 10, 100, 3)
    expect(bars).toHaveLength(100)
    expect(bars[10]!.who).toBe('cv')
    expect(bars[55]!.who).toBe('gap')
    expect(bars[80]!.who).toBe('caller')
    expect(bars.every(b => b.a >= 0 && b.a <= 1)).toBe(true)
  })

  it('turns a card-number cut into a hush band', () => {
    const turns = withHushes([{ who: 'caller' as const, from: 41.2, to: 46.6, hush: 44.6 }])
    expect(turns).toEqual([{ who: 'caller', from: 41.2, to: 44.6 }, { who: 'hush', from: 44.6, to: 46.6 }])
    const bars = conversationBars(turns, 50, 50)
    expect(bars[45]!.who).toBe('hush')
    expect(bars[45]!.a).toBe(0)
  })

  it('splits mono peaks into ClaimVoice and caller lanes by who spoke, and blanks the hush', () => {
    const lanes = splitPeaks([0.5, 0.6, 0.7, 0.8], 4, [
      { speaker: 'line', startSeconds: 0, endSeconds: 2 },
      { speaker: 'caller', startSeconds: 2, endSeconds: 4 },
    ], [[3, 4]])
    expect(lanes.line).toEqual([0.5, 0.6, 0, 0])
    expect(lanes.caller).toEqual([0, 0, 0.7, 0])
    expect(lanes.hushed).toEqual([false, false, false, true])
  })
})

describe('live levels', () => {
  it('keeps a fixed-size ring with the newest bar last', () => {
    const ring = new LiveBars(3)
    ring.push({ who: 'cv', a: 0.5 })
    ring.push({ who: 'caller', a: 0.7 })
    expect(ring.bars).toHaveLength(3)
    expect(ring.bars[2]).toEqual({ who: 'caller', a: 0.7 })
    ring.resize(5)
    expect(ring.bars).toHaveLength(5)
    expect(ring.bars[4]).toEqual({ who: 'caller', a: 0.7 })
  })

  it('reads RMS from a frame and maps it to the five-step reduced-motion meter', () => {
    expect(rmsLevel(new Float32Array(256))).toBe(0)
    const loud = new Float32Array(256).fill(0.5)
    expect(rmsLevel(loud)).toBeGreaterThan(0.9)
    expect(levelStep(0)).toBe(0)
    expect(levelStep(0.5)).toBe(3)
    expect(levelStep(2)).toBe(5)
  })

  it('stays near silent in a pause and speech-like in a turn', () => {
    const r = rng(1)
    expect(syntheticLevel('gap', 1, r)).toBeLessThan(0.1)
    const speech = syntheticLevel('cv', 1.3, r)
    expect(speech).toBeGreaterThanOrEqual(0.25)
    expect(speech).toBeLessThanOrEqual(1)
    const rhythm = defaultRhythm(5)
    expect(new Set(Array.from({ length: 140 }, (_, i) => rhythm(i * 0.1)))).toEqual(new Set(['caller', 'cv', 'gap']))
  })
})

describe('recording pins', () => {
  it('keeps pins inside the band and moves overlapping ones to a second row', () => {
    const out = layoutPins([{ x: 0, label: 'Consent' }, { x: 0.02, label: 'Policy found' }, { x: 1, label: 'Read-back' }], 600)
    expect(out[0]!.left).toBe(0)
    expect(out[1]!.row).toBe(1)
    expect(out[2]!.left + out[2]!.width).toBeLessThanOrEqual(600)
    expect(pinWidth('Consent')).toBeGreaterThan(40)
  })
})

describe('silent audio for unrecorded calls', () => {
  it('writes a valid WAV header of the right length', () => {
    const wav = silentWav(2, 1000)
    const text = (o: number) => String.fromCharCode(...wav.slice(o, o + 4))
    expect(text(0)).toBe('RIFF')
    expect(text(8)).toBe('WAVE')
    expect(wav.length).toBe(44 + 2000)
    expect(new DataView(wav.buffer).getUint32(24, true)).toBe(1000)
  })
})
