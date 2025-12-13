// Server-sent events over fetch (not EventSource), so the app can read X-ClaimVoice-Now, send Last-Event-ID on
// reconnect, and treat `resync` and gaps itself. Framing per the contract §1.8: `retry: 3000` first, then
// `id:` / `event:` / `data:` frames, `event: ping` every 15 s.
import { syncFromHeader } from './demoClock'

export interface SseEvent { id: string | null, event: string, data: string }

/** Incremental SSE parser: feed text chunks, get complete events back. */
export class SseParser {
  private buffer = ''
  private id: string | null = null
  private event = ''
  private data: string[] = []
  retry: number | null = null
  lastEventId: string | null = null

  feed(chunk: string): SseEvent[] {
    this.buffer += chunk
    const out: SseEvent[] = []
    let nl: number
    while ((nl = this.buffer.search(/\r\n|\r|\n/)) >= 0) {
      const line = this.buffer.slice(0, nl)
      const sepLen = this.buffer.startsWith('\r\n', nl) ? 2 : 1
      this.buffer = this.buffer.slice(nl + sepLen)
      if (line === '') {
        if (this.data.length || this.event) {
          const ev = { id: this.id, event: this.event || 'message', data: this.data.join('\n') }
          if (this.id !== null) this.lastEventId = this.id
          out.push(ev)
        }
        this.id = null
        this.event = ''
        this.data = []
        continue
      }
      if (line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon < 0 ? line : line.slice(0, colon)
      let value = colon < 0 ? '' : line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'data') this.data.push(value)
      else if (field === 'event') this.event = value
      else if (field === 'id') this.id = value
      else if (field === 'retry' && /^\d+$/.test(value)) this.retry = Number(value)
    }
    return out
  }
}

export interface StreamHandle { close(): void }
export interface StreamOptions {
  onEvent: (ev: SseEvent) => void
  onStatus?: (status: 'connecting' | 'open' | 'lost') => void
  lastEventId?: string | null
  /** Back-off between reconnects, ms (doubles to 30 s). */
  retryMs?: number
}

/** Open an SSE stream with automatic reconnect. Returns a handle to close it. */
export function openStream(url: string, opts: StreamOptions): StreamHandle {
  let closed = false
  let controller: AbortController | null = null
  let lastId = opts.lastEventId ?? null
  let delay = opts.retryMs ?? 3000
  let timer: ReturnType<typeof setTimeout> | null = null

  const connect = async () => {
    if (closed) return
    opts.onStatus?.('connecting')
    controller = new AbortController()
    const parser = new SseParser()
    try {
      const headers: Record<string, string> = { Accept: 'text/event-stream' }
      if (lastId) headers['Last-Event-ID'] = lastId
      const res = await fetch(url, { headers, credentials: 'same-origin', signal: controller.signal })
      syncFromHeader(res.headers.get('X-ClaimVoice-Now'))
      if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)
      opts.onStatus?.('open')
      delay = opts.retryMs ?? 3000
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        for (const ev of parser.feed(decoder.decode(value, { stream: true }))) {
          if (ev.id) lastId = ev.id
          opts.onEvent(ev)
        }
        if (parser.retry) delay = parser.retry
      }
    }
    catch {
      if (closed) return
    }
    if (closed) return
    opts.onStatus?.('lost')
    timer = setTimeout(connect, delay)
    delay = Math.min(30_000, delay * 2)
  }
  void connect()
  return {
    close() {
      closed = true
      if (timer) clearTimeout(timer)
      controller?.abort()
    },
  }
}
