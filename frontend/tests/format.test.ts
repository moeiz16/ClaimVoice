import { describe, expect, it } from 'vitest'
import {
  emphasis, firstName, fmtAgo, fmtClock, fmtDate, fmtDateShort, fmtDayGroup, fmtDayLong, fmtDayShort, fmtDayTime,
  fmtDurationWords, fmtTime, frequency, initials, joinWords, money, pct, secondsSince, zoneForRegion, zoneLabel,
} from '../app/utils/format'

// 14:42 UTC on Thursday 8 January 2026 is 7:42 a.m. in Calgary and Denver, 9:42 a.m. in Montréal.
const DEMO = '2026-01-08T14:42:00Z'

describe('clock and duration words', () => {
  it('formats seconds as m:ss and h:mm:ss', () => {
    expect(fmtClock(76)).toBe('1:16')
    expect(fmtClock(5)).toBe('0:05')
    expect(fmtClock(3725)).toBe('1:02:05')
  })

  it('reads bad input as zero', () => {
    expect(fmtClock(-4)).toBe('0:00')
    expect(fmtClock(Number.NaN)).toBe('0:00')
    expect(fmtClock(null)).toBe('0:00')
  })

  it('says durations in words', () => {
    expect(fmtDurationWords(76)).toBe('1 minute 16')
    expect(fmtDurationWords(384)).toBe('6 minutes 24')
    expect(fmtDurationWords(120)).toBe('2 minutes')
    expect(fmtDurationWords(45)).toBe('45 seconds')
    expect(fmtDurationWords(76, 'fr')).toBe('1 min 16')
  })
})

describe('times in the right zone, never the browser\'s', () => {
  it('shows Calgary time with a.m./p.m.', () => {
    expect(fmtTime(DEMO)).toBe('7:42 a.m.')
    expect(fmtTime('2026-01-08T00:52:00Z', 'America/Denver')).toBe('5:52 p.m.')
  })

  it('shows Montréal time for Québec', () => {
    expect(fmtTime(DEMO, zoneForRegion('CA-QC'))).toBe('9:42 a.m.')
  })

  it('uses the French clock style', () => {
    expect(fmtTime(DEMO, 'America/Edmonton', 'fr')).toBe('7 h 42')
  })

  it('handles midnight and noon', () => {
    expect(fmtTime('2026-01-08T07:00:00Z')).toBe('12:00 a.m.')
    expect(fmtTime('2026-01-08T19:05:00Z')).toBe('12:05 p.m.')
  })

  it('names days in English and French', () => {
    expect(fmtDayLong(DEMO)).toBe('Thursday 8 January')
    expect(fmtDayLong(DEMO, 'America/Edmonton', 'fr')).toBe('jeudi 8 janvier')
    expect(fmtDayShort('2026-01-08T00:52:00Z', 'America/Denver')).toBe('Wed 7 Jan')
    expect(fmtDayTime('2026-01-08T00:52:00Z', 'America/Denver')).toBe('Wed 7 Jan, 5:52 p.m.')
  })

  it('reads calendar dates without shifting them', () => {
    expect(fmtDate('2025-12-27')).toBe('27 Dec 2025')
    expect(fmtDateShort('2026-01-05')).toBe('Mon 5 Jan')
    expect(fmtDate(null)).toBe('')
  })

  it('groups activity by day relative to demo now', () => {
    const now = new Date(DEMO)
    expect(fmtDayGroup('2026-01-08T15:00:00Z', now)).toBe('Today')
    expect(fmtDayGroup('2026-01-07T20:00:00Z', now)).toBe('Yesterday')
    expect(fmtDayGroup('2026-01-05T20:00:00Z', now)).toBe('Monday 5 January')
  })

  it('maps regions to zones and labels', () => {
    expect(zoneForRegion('US-CO')).toBe('America/Denver')
    expect(zoneForRegion(null)).toBe('America/Edmonton')
    expect(zoneLabel('CA-QC')).toBe('Montréal time')
    expect(zoneLabel('CA-AB', 'fr')).toBe('heure de Calgary')
  })

  it('measures time since in demo time', () => {
    const now = new Date(DEMO)
    expect(secondsSince('2026-01-08T14:41:22Z', now)).toBe(38)
    expect(secondsSince('2026-01-08T15:00:00Z', now)).toBe(0)
    expect(fmtAgo('2026-01-08T14:39:00Z', now)).toBe('3 minutes ago')
    expect(fmtAgo('2026-01-08T14:41:50Z', now)).toBe('just now')
  })
})

describe('plain words for numbers and names', () => {
  it('expresses rates as frequencies, never decimals', () => {
    expect(frequency(0.96)).toBe('96 in 100')
    expect(frequency(0.7, 10)).toBe('7 in 10')
    expect(frequency(1.4)).toBe('100 in 100')
    expect(pct(0.041)).toBe('4.1%')
  })

  it('formats money with currency', () => {
    expect(money(4000)).toBe('$4,000')
    expect(money(9000, 'USD')).toBe('US$9,000')
  })

  it('makes initials and lists', () => {
    expect(initials('Renée Kowalchuk')).toBe('RK')
    expect(initials('Cher')).toBe('C')
    expect(initials('')).toBe('·')
    expect(joinWords(['Jamal', 'Sofía', 'Aurélie'])).toBe('Jamal, Sofía and Aurélie')
    expect(joinWords(['Jamal', 'Sofía'], 'fr')).toBe('Jamal et Sofía')
    expect(firstName('Tomás Reyes')).toBe('Tomás')
  })

  it('splits **emphasis** out of answer sentences', () => {
    expect(emphasis('Of 1,240, **1,191 closed** without help.')).toEqual([
      { text: 'Of 1,240, ', em: false }, { text: '1,191 closed', em: true }, { text: ' without help.', em: false },
    ])
    expect(emphasis('no emphasis')).toEqual([{ text: 'no emphasis', em: false }])
  })
})
