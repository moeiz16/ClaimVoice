// The typed HTTP layer for /api/v1: same-origin cookies, X-CSRF-Token on unsafe methods, RFC 7807 errors, the
// X-ClaimVoice-Now clock header, Accept-Language. When the mock is switched on (NUXT_PUBLIC_API_MOCK=1) requests go
// to the in-browser mock instead (loaded lazily, so it never ships in the normal path).
import type { Problem } from '~/types/api'
import { syncFromHeader } from './demoClock'
import { openStream, type StreamHandle, type StreamOptions } from './sse'

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly problem: Problem | null
  constructor(status: number, problem: Problem | null, fallback = 'Something went wrong.') {
    super(problem?.detail || problem?.title || fallback)
    this.status = status
    this.code = problem?.code ?? (status === 0 ? 'network' : 'error')
    this.problem = problem
  }

  fieldError(field: string): string | null {
    return this.problem?.errors?.find(e => e.field === field)?.message ?? null
  }
}

export interface RequestOpts {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, string | number | boolean | null | undefined>
  body?: unknown
  /** Bearer token for caller-leg endpoints (exempt from CSRF). */
  bearer?: string
  /** Return the raw Response (for downloads). */
  raw?: boolean
  signal?: AbortSignal
}

export interface MockResponse { status: number, body: unknown, headers?: Record<string, string> }
export interface MockBackend {
  fetch(method: string, path: string, query: URLSearchParams, body: unknown): Promise<MockResponse>
  stream(path: string, opts: StreamOptions): StreamHandle
}

let mockOn = false
let mockBackend: MockBackend | null = null
let uiLang: 'en' | 'fr' = 'en'

export function setMockMode(on: boolean, backend: MockBackend | null = null): void {
  mockOn = on
  if (backend) mockBackend = backend
}
export function isMockMode(): boolean { return mockOn }
export function setUiLang(lang: 'en' | 'fr'): void { uiLang = lang }

async function mock(): Promise<MockBackend> {
  if (!mockBackend) {
    const mod = await import('~/mock/router')
    mockBackend = mod.createMockBackend()
  }
  return mockBackend
}

export function readCookie(name: string, cookie: string = typeof document === 'undefined' ? '' : document.cookie): string | null {
  for (const part of cookie.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === name) return decodeURIComponent(v.join('='))
  }
  return null
}

export function buildQuery(query: RequestOpts['query']): string {
  if (!query) return ''
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  const s = qs.toString()
  return s ? `?${s}` : ''
}

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

async function ensureCsrf(): Promise<string | null> {
  let token = readCookie('cv_csrf')
  if (!token) {
    const res = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'same-origin' })
    syncFromHeader(res.headers.get('X-ClaimVoice-Now'))
    token = readCookie('cv_csrf')
  }
  return token
}

async function parseProblem(res: Response): Promise<Problem | null> {
  try {
    const ct = res.headers.get('content-type') ?? ''
    if (ct.includes('json')) return (await res.json()) as Problem
  }
  catch { /* not JSON */ }
  return null
}

export async function apiFetch<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const method = opts.method ?? 'GET'
  if (mockOn) {
    const backend = await mock()
    const res = await backend.fetch(method, path, new URLSearchParams(buildQuery(opts.query).slice(1)), opts.body)
    syncFromHeader(res.headers?.['X-ClaimVoice-Now'])
    if (res.status >= 400) throw new ApiError(res.status, res.body as Problem)
    return res.body as T
  }
  const headers: Record<string, string> = { 'Accept': 'application/json', 'Accept-Language': uiLang }
  const isForm = typeof FormData !== 'undefined' && opts.body instanceof FormData
  if (opts.body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (opts.bearer) headers.Authorization = `Bearer ${opts.bearer}`
  else if (UNSAFE.has(method)) {
    const token = await ensureCsrf()
    if (token) headers['X-CSRF-Token'] = token
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
      signal: opts.signal,
    })
  }
  catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, null, 'We could not reach ClaimVoice. Check your connection and try again.')
  }
  syncFromHeader(res.headers.get('X-ClaimVoice-Now'))
  if (!res.ok) throw new ApiError(res.status, await parseProblem(res))
  if (opts.raw) return res as unknown as T
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') ?? ''
  return (ct.includes('json') ? await res.json() : await res.text()) as T
}

/** Open a server-sent event stream under /api/v1 (or the mock's simulated stream). */
export function apiStream(path: string, opts: StreamOptions): StreamHandle {
  if (mockOn) {
    let handle: StreamHandle | null = null
    let closed = false
    void mock().then((b) => { if (!closed) handle = b.stream(path, opts) })
    return { close() { closed = true; handle?.close() } }
  }
  return openStream(`${API_BASE}${path}`, opts)
}

