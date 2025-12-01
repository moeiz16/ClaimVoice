import { afterEach, describe, expect, it } from 'vitest'
import { demoNow, resetDemoClock, syncFromHeader } from '../app/utils/demoClock'

describe('demo clock', () => {
  afterEach(() => resetDemoClock())

  it('follows the server clock header', () => {
    const browser = Date.parse('2026-03-14T09:00:00Z')
    syncFromHeader('2026-01-08T09:00:00Z', browser)
    expect(demoNow(browser + 60_000).toISOString()).toBe('2026-01-08T09:01:00.000Z')
  })

  it('ignores a missing or invalid header', () => {
    syncFromHeader(null)
    syncFromHeader('not a date')
    const t = Date.parse('2026-01-08T10:00:00Z')
    expect(demoNow(t).getTime()).toBe(t)
  })
})
