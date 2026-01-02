// The caller leg of a browser call (docs/API_CONTRACT.md Part 4). SmallWebRTC: one RTCPeerConnection with the
// microphone track (unless typed) and an ordered data channel "claimvoice"; SDP offer/answer over HTTP with the
// caller's bearer token; trickle ICE batched every 100 ms; once the channel opens, client.hello and then the text
// "ping-<ms>" about every second. If WebRTC can't connect within 8 s, the WebSocket fallback carries the same JSON.
import type { ClientMessage, ConnectInfo, ServerMessage } from '~/types/api'

export interface CallTransport {
  readonly kind: 'webrtc' | 'websocket' | 'local'
  send(msg: ClientMessage): void
  close(): void
}

export interface TransportEvents {
  onMessage: (msg: ServerMessage) => void
  /** The leg is open; `t` can send already (the caller's hello goes first, before the connect call returns). */
  onOpen: (t: CallTransport) => void
  onClose: (reason: string) => void
  onRemoteAudio?: (stream: MediaStream) => void
}

export function parseServerMessage(data: unknown): ServerMessage | null {
  if (typeof data !== 'string') return null
  try {
    const m = JSON.parse(data) as ServerMessage
    return m && typeof m === 'object' && typeof (m as { type?: unknown }).type === 'string' ? m : null
  }
  catch { return null }
}

export function pingFrame(now: number = Date.now()): string {
  return `ping-${now}`
}

export class IceBatcher {
  private queue: RTCIceCandidateInit[] = []
  private timer: ReturnType<typeof setTimeout> | null = null
  constructor(private flushFn: (c: RTCIceCandidateInit[]) => void, private delayMs = 100) {}
  add(c: RTCIceCandidateInit) {
    this.queue.push(c)
    if (!this.timer) this.timer = setTimeout(() => this.flush(), this.delayMs)
  }

  flush() {
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    if (!this.queue.length) return
    const batch = this.queue
    this.queue = []
    this.flushFn(batch)
  }

  hold() { if (this.timer) { clearTimeout(this.timer); this.timer = null } }
}

async function bearerJson<T>(url: string, method: 'POST' | 'PATCH', token: string, body: unknown): Promise<T> {
  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(`signalling ${res.status}`)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export async function connectWebRtc(info: ConnectInfo, mic: MediaStream | null, ev: TransportEvents, timeoutMs = 8000): Promise<CallTransport> {
  const pc = new RTCPeerConnection({ iceServers: info.iceServers.map(s => ({ urls: s.urls, username: s.username ?? undefined, credential: s.credential ?? undefined })) })
  if (mic) for (const t of mic.getAudioTracks()) pc.addTrack(t, mic)
  else pc.addTransceiver('audio', { direction: 'recvonly' })
  const dc = pc.createDataChannel(info.dataChannelLabel || 'claimvoice', { ordered: true })
  let pcId: string | null = null
  const pending: RTCIceCandidateInit[] = []
  const batcher = new IceBatcher((candidates) => {
    if (!pcId) { pending.push(...candidates); return }
    void bearerJson(info.iceUrl, 'PATCH', info.callerToken, { pcId, candidates: candidates.map(c => ({ candidate: c.candidate, sdpMid: c.sdpMid, sdpMLineIndex: c.sdpMLineIndex })) }).catch(() => null)
  })
  pc.onicecandidate = (e) => { if (e.candidate) batcher.add(e.candidate.toJSON()) }
  pc.ontrack = (e) => { if (e.streams[0]) ev.onRemoteAudio?.(e.streams[0]) }
  let ping: ReturnType<typeof setInterval> | null = null
  let closed = false
  const close = (reason: string) => {
    if (closed) return
    closed = true
    if (ping) clearInterval(ping)
    try { dc.close() } catch { /* already closed */ }
    pc.close()
    ev.onClose(reason)
  }

  const opened = new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), timeoutMs)
    dc.onopen = () => {
      clearTimeout(t)
      ping = setInterval(() => { if (dc.readyState === 'open') dc.send(pingFrame()) }, 1000)
      resolve()
    }
  })
  dc.onmessage = (e) => { const m = parseServerMessage(e.data); if (m) ev.onMessage(m) }
  dc.onclose = () => close('closed')
  pc.onconnectionstatechange = () => { if (pc.connectionState === 'failed') close('failed') }

  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  const answer = await bearerJson<{ sdp: string, type: 'answer', pcId: string }>(info.offerUrl, 'POST', info.callerToken, { sdp: offer.sdp, type: 'offer' })
  pcId = answer.pcId
  await pc.setRemoteDescription({ sdp: answer.sdp, type: 'answer' })
  if (pending.length) { const p = pending.splice(0); batcher.add(p[0]!); p.slice(1).forEach(c => batcher.add(c)) }
  try { await opened }
  catch (e) { close('timeout'); throw e }
  const transport: CallTransport = {
    kind: 'webrtc',
    send: (msg) => { if (dc.readyState === 'open') dc.send(JSON.stringify(msg)) },
    close: () => close('hangup'),
  }
  ev.onOpen(transport)
  return transport
}

export function connectWebSocket(info: ConnectInfo, ev: TransportEvents): Promise<CallTransport> {
  return new Promise((resolve, reject) => {
    const url = new URL(info.websocketUrl, window.location.href)
    if (!url.searchParams.has('token')) url.searchParams.set('token', info.callerToken)
    url.protocol = url.protocol === 'https:' ? 'wss:' : url.protocol === 'http:' ? 'ws:' : url.protocol
    const ws = new WebSocket(url.toString())
    let open = false
    ws.onopen = () => {
      open = true
      const transport: CallTransport = { kind: 'websocket', send: m => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(m)), close: () => ws.close(1000) }
      ev.onOpen(transport)
      resolve(transport)
    }
    ws.onmessage = (e) => { const m = parseServerMessage(e.data); if (m) ev.onMessage(m) }
    ws.onerror = () => { if (!open) reject(new Error('websocket')) }
    ws.onclose = e => ev.onClose(e.code === 1000 ? 'hangup' : `closed ${e.code}`)
  })
}
