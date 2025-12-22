import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, buildQuery, readCookie, setMockMode } from '../app/utils/http'
import { demoNow, resetDemoClock } from '../app/utils/demoClock'
import { IceBatcher, parseServerMessage, pingFrame } from '../app/utils/voiceTransport'
import { fitWithin, needsConversion } from '../app/utils/photos'
import { landingFor, navFor } from '../app/composables/useSession'
import { routeStyle, statusStyle } from '../app/utils/labels'

describe('the HTTP layer', () => {
  afterEach(() => { vi.unstubAllGlobals(); resetDemoClock() })

  it('builds query strings without empty values', () => {
    expect(buildQuery({ route: 'adjuster', q: '', page: 2, x: null, y: undefined })).toBe('?route=adjuster&page=2')
    expect(buildQuery(undefined)).toBe('')
  })

  it('reads the CSRF cookie', () => {
    expect(readCookie('cv_csrf', 'a=1; cv_csrf=tok%3D; b=2')).toBe('tok=')
    expect(readCookie('cv_csrf', 'a=1')).toBeNull()
  })

  it('sends X-CSRF-Token on unsafe requests, syncs the demo clock and parses problems', async () => {
    document.cookie = 'cv_csrf=abc'
    const calls: { url: string, init: RequestInit }[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init })
      return new Response(JSON.stringify({ code: 'validation_error', status: 422, title: 'Validation failed', type: '', detail: 'Give a reason.', errors: [{ field: 'reason', message: 'Give a reason for the change.' }] }), {
        status: 422, headers: { 'content-type': 'application/problem+json', 'X-ClaimVoice-Now': '2026-01-08T14:42:00Z' },
      })
    }))
    const err = await apiFetch('/claims/1/routing/override', { method: 'POST', body: { route: 'adjuster', reason: '' } }).catch(e => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe('validation_error')
    expect((err as ApiError).fieldError('reason')).toBe('Give a reason for the change.')
    expect((calls[0]!.init.headers as Record<string, string>)['X-CSRF-Token']).toBe('abc')
    expect(calls[0]!.url).toBe('/api/v1/claims/1/routing/override')
    expect(Math.abs(demoNow().getTime() - Date.parse('2026-01-08T14:42:00Z'))).toBeLessThan(5000)
  })

  it('uses a bearer token instead of CSRF on caller-leg requests', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await apiFetch('/calls/x/hangup', { method: 'POST', body: {}, bearer: 'tok' })
    const headers = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer tok')
    expect(headers['X-CSRF-Token']).toBeUndefined()
  })

  it('turns a network failure into a plain-words error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    const err = await apiFetch('/meta').catch(e => e) as ApiError
    expect(err.status).toBe(0)
    expect(err.message).toMatch(/could not reach ClaimVoice/)
  })
})

describe('the local mock API', () => {
  beforeEach(() => setMockMode(true))
  afterEach(() => setMockMode(false))

  it('serves the seeded sample organisation behind sign-in and permissions', async () => {
    await expect(apiFetch('/switchboard')).rejects.toMatchObject({ status: 401 })
    await expect(apiFetch('/auth/login', { method: 'POST', body: { email: 'renee.kowalchuk@larkspurmutual.ca', password: 'nope' } })).rejects.toMatchObject({ code: 'invalid_credentials' })
    const me = await apiFetch<{ membership: { role: string } }>('/auth/demo', { method: 'POST', body: { role: 'adjuster' } })
    expect(me.membership.role).toBe('adjuster')
    await expect(apiFetch('/qa/queue')).rejects.toMatchObject({ status: 403 })
    const claims = await apiFetch<{ items: { claimNumber: string, siuOpen: boolean }[], total: number }>('/claims', { query: { q: 'CV-26-01856' } })
    expect(claims.items[0]!.claimNumber).toBe('CV-26-01856')
    expect(claims.items[0]!.siuOpen).toBe(false)
  })

  it('requires a reason to change a route, and logs the change', async () => {
    await apiFetch('/auth/demo', { method: 'POST', body: { role: 'supervisor' } })
    const page = await apiFetch<{ items: { id: string }[] }>('/claims', { query: { q: 'CV-26-01842' } })
    const id = page.items[0]!.id
    await expect(apiFetch(`/claims/${id}/routing/override`, { method: 'POST', body: { route: 'adjuster', reason: ' ' } })).rejects.toMatchObject({ code: 'validation_error' })
    const d = await apiFetch<{ route: string, override: { reason: string } }>(`/claims/${id}/routing/override`, { method: 'POST', body: { route: 'adjuster', reason: 'Photos show more damage' } })
    expect(d.route).toBe('adjuster')
    const audit = await apiFetch<{ items: { action: string }[] }>('/audit').catch(() => null)
    expect(audit).toBeNull() // supervisors can't read the audit log
  })
})

describe('the caller leg', () => {
  it('parses server messages and ignores anything else', () => {
    expect(parseServerMessage('{"type":"line.say","turnId":"t","text":"Hi"}')?.type).toBe('line.say')
    expect(parseServerMessage('ping-123')).toBeNull()
    expect(parseServerMessage(42)).toBeNull()
  })

  it('sends the keep-alive as ping-<ms>', () => {
    expect(pingFrame(1736347320000)).toBe('ping-1736347320000')
  })

  it('batches ICE candidates', async () => {
    const sent: number[] = []
    const b = new IceBatcher(c => sent.push(c.length), 10)
    b.add({ candidate: 'a' })
    b.add({ candidate: 'b' })
    await new Promise(r => setTimeout(r, 30))
    b.add({ candidate: 'c' })
    b.flush()
    expect(sent).toEqual([2, 1])
  })
})

describe('photos from the caller\'s phone', () => {
  it('converts HEIC and very large photos, keeps small JPEGs', () => {
    expect(needsConversion({ type: 'image/heic', name: 'IMG_1.HEIC', size: 1000 })).toBe(true)
    expect(needsConversion({ type: '', name: 'IMG_2.heif', size: 1000 })).toBe(true)
    expect(needsConversion({ type: 'image/jpeg', name: 'a.jpg', size: 6_000_000 })).toBe(true)
    expect(needsConversion({ type: 'image/jpeg', name: 'a.jpg', size: 900_000 })).toBe(false)
  })

  it('fits photos inside 2400 px without stretching', () => {
    expect(fitWithin(4032, 3024)).toEqual({ w: 2400, h: 1800 })
    expect(fitWithin(800, 600)).toEqual({ w: 800, h: 600 })
  })
})

describe('roles and words', () => {
  const me = (role: string, name = 'Priya Sandhu') => ({ user: { fullName: name }, membership: { role } }) as never
  it('lands each role on its home screen', () => {
    expect(landingFor(me('supervisor'))).toBe('/lines')
    expect(landingFor(me('adjuster'))).toBe('/claims')
    expect(landingFor(me('siu_investigator'))).toBe('/claims?route=special_investigation')
    expect(landingFor(me('compliance'))).toBe('/routing')
    expect(landingFor(me('compliance', 'Owen Fairweather'))).toBe('/quality')
    expect(landingFor(me('admin'))).toBe('/settings')
    expect(landingFor(null)).toBe('/lines')
  })

  it('shows only the dock destinations a person can use', () => {
    expect(navFor(['claims:read', 'models:read'])).toEqual({ lines: false, claims: true, quality: false, routing: true, settings: false })
  })

  it('pairs every route and status with an icon and a word', () => {
    expect(routeStyle('fast_track')).toEqual({ kind: 'fast', icon: 'check', label: 'Fast-track' })
    expect(routeStyle('special_investigation').label).toBe('Closer look')
    expect(statusStyle('watch')).toEqual({ kind: 'siu', icon: 'clock' })
    expect(statusStyle('act').icon).toBe('urgent')
  })
})
