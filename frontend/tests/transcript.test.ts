import { describe, expect, it } from 'vitest'
import {
  findPhrase, karaoke, karaokeRuns, phraseSpokenAt, segmentText, settleSplit, stripCardToken, turnAt, turnAtMs,
} from '../app/utils/transcript'
import { marksByTurn, sectionDone, slotByKey } from '../app/utils/marks'
import type { ClaimFile, Slot } from '../app/types/api'

describe('transcript segments', () => {
  it('marks heard spans, sound tags and removed card numbers, as text only', () => {
    const text = 'Parked on the street. [dog barking] It\'s [card number removed]'
    const segs = segmentText(text, [{ start: 0, end: 20, key: 'parked' }])
    expect(segs).toEqual([
      { type: 'span', text: 'Parked on the street', key: 'parked', kind: 'heard' },
      { type: 'text', text: '. ' },
      { type: 'sound', text: '[dog barking]' },
      { type: 'text', text: ' It\'s ' },
      { type: 'hush' },
    ])
  })

  it('never renders caller text as markup', () => {
    const segs = segmentText('<b>bold</b> & <script>x</script>')
    expect(segs).toEqual([{ type: 'text', text: '<b>bold</b> & <script>x</script>' }])
  })

  it('drops overlapping and out-of-range marks safely', () => {
    const segs = segmentText('abcdef', [{ start: 0, end: 4, key: 'a' }, { start: 2, end: 5, key: 'b' }, { start: 4, end: 99, key: 'c' }])
    expect(segs.map(s => (s.type === 'span' ? s.key : s.type))).toEqual(['a', 'c'])
  })

  it('finds phrases case-insensitively', () => {
    expect(findPhrase('The Trunk won\'t close', 'trunk')).toEqual({ start: 4, end: 9 })
    expect(findPhrase('abc', 'zzz')).toBeNull()
  })

  it('knows which turn is speaking', () => {
    const turns = [{ from: 0 }, { from: 5 }, { from: 9 }]
    expect(turnAt(turns, -1)).toBe(-1)
    expect(turnAt(turns, 6)).toBe(1)
    expect(turnAtMs([{ atMs: 0 }, { atMs: 3000 }], 4000)).toBe(1)
  })
})

describe('karaoke captions', () => {
  const turn = { text: 'It\'s L-M, two-oh-four, one-one-eight.', from: 10, to: 14, spans: [{ text: 'L-M, two-oh-four, one-one-eight.', key: 'policy' }] }

  it('lights spoken words and keeps the rest faint', () => {
    const k = karaoke(turn, 11)
    expect(k.words[0]!.ahead).toBe(false)
    expect(k.words[3]!.ahead).toBe(true)
  })

  it('marks a heard span only once all its words are said', () => {
    expect(karaoke(turn, 12).words.some(w => w.span)).toBe(false)
    const done = karaoke(turn, 14)
    expect(done.words.filter(w => w.span === 'policy')).toHaveLength(3)
    expect(karaokeRuns(done.words).map(r => r.span)).toEqual([null, 'policy'])
  })

  it('collapses the card digits into the hush once the cut starts', () => {
    const t = { text: 'Do you need my card? It\'s [card number removed]', from: 40, to: 46, hush: 44 }
    expect(karaoke(t, 43).hushed).toBe(false)
    expect(karaoke(t, 45).hushed).toBe(true)
    expect(karaoke(t, 45).words.map(w => w.text).join(' ')).not.toContain('[card')
    expect(stripCardToken('It\'s [card number removed] ok')).toBe('It\'s ok')
  })

  it('knows when a phrase finishes being spoken', () => {
    const at = phraseSpokenAt({ text: 'one two three four', from: 0, to: 4 }, 'two three')
    expect(at).toBeCloseTo(2.5)
    expect(phraseSpokenAt({ text: 'one two', from: 0, to: 2 }, 'nine')).toBeNull()
  })

  it('splits final words from interim words for Settle', () => {
    expect(settleSplit('Around eleven', 'I think I')).toEqual({ final: ['Around', 'eleven'], interim: ['I', 'think', 'I'] })
  })
})

describe('claim-file links into the transcript', () => {
  const slot = (key: string, span: Slot['span'], display = 'x', required = true): Slot => ({
    key, label: key, value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: span ? 'heard' : 'policy_record',
    sourceLabel: span ? '▸ 0:31' : 'from the policy', span, heardAtSeconds: span ? 31 : null, changedAtSeconds: null, confirmed: true, required, history: [],
  })
  const file: ClaimFile = {
    callId: 'c', claimId: null, lossType: 'wind', lossTypeLabel: 'Wind', progress: 0.5, missing: [],
    sections: [{ key: 'policy', label: 'Policy', slots: [slot('policy_number', { turnId: 't1', start: 5, end: 17 }), slot('address', null)] }],
  }

  it('builds marks per turn from heard values only', () => {
    expect(marksByTurn(file)).toEqual({ t1: [{ start: 5, end: 17, key: 'policy_number' }] })
    expect(marksByTurn(file, [{ turnId: 't2', start: 0, end: 4, key: 'sign', kind: 'sign' }]).t2![0]!.kind).toBe('sign')
  })

  it('finds a value by key and knows when a section is complete', () => {
    expect(slotByKey(file, 'address')?.sourceLabel).toBe('from the policy')
    expect(slotByKey(file, 'nope')).toBeNull()
    expect(sectionDone(file.sections[0]!.slots)).toBe(true)
    expect(sectionDone([slot('a', null, '')])).toBe(false)
  })
})
