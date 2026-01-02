// "Ring the demo line": a live browser call. browser_speech mode by default (SpeechRecognition for the caller's
// words, speechSynthesis for ClaimVoice's turns, the microphone also sent for the recording and barge-in), typed mode
// when recognition is missing or the caller prefers it. States: idle → starting → ringing → consent/listening ⇄
// speaking → ended; plus blocked (microphone refused), busy (all demo lines in use) and lost.
import type { CallMode, ClientMessage, EndRoute, Lang, ServerMessage, Slot, StageInfo } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError, isMockMode } from '~/utils/http'
import { connectWebRtc, connectWebSocket, type CallTransport, type TransportEvents } from '~/utils/voiceTransport'

export type DemoState = 'idle' | 'starting' | 'ringing' | 'listening' | 'speaking' | 'ended' | 'blocked' | 'busy' | 'lost'
export interface CaptionLine { id: string, who: 'cv' | 'caller', text: string, final: boolean }

interface Recognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  start(): void
  stop(): void
  abort(): void
  onresult: ((e: { resultIndex: number, results: ArrayLike<{ isFinal: boolean, 0: { transcript: string, confidence: number } }> }) => void) | null
  onspeechstart: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognitionCtor = new () => Recognition

export function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor, webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function useDemoCall() {
  const state = ref<DemoState>('idle')
  const mode = ref<CallMode>('browser_speech')
  const lang = ref<Lang>('en')
  const lines = ref<CaptionLine[]>([])
  const interim = ref('')
  const stage = ref<StageInfo | null>(null)
  const slip = ref<Slot[]>([])
  const notice = ref<string | null>(null)
  const hushed = ref(false)
  const ended = ref<{ claimNumber: string | null, summary: string | null, nextSteps: string[], route: EndRoute | null } | null>(null)
  const muted = ref(false)
  const error = ref<string | null>(null)
  const noRecognition = ref(false)
  const startedAt = ref<number | null>(null)
  const maxSeconds = ref(360)
  const mic = useMicLevel()
  let transport: CallTransport | null = null
  let rec: Recognition | null = null
  let speakingTurn: string | null = null
  let t0 = 0
  let wantRecognition = false

  const ms = () => Math.round(performance.now() - t0)
  const send = (m: ClientMessage) => transport?.send(m)
  const voices = () => (typeof speechSynthesis !== 'undefined' ? speechSynthesis.getVoices().filter(v => /^(en|fr)-CA/i.test(v.lang)).map(v => v.name) : [])

  function startRecognition() {
    const Ctor = recognitionCtor()
    if (!Ctor || mode.value !== 'browser_speech') return
    wantRecognition = true
    if (rec) return
    rec = new Ctor()
    rec.lang = lang.value === 'fr' ? 'fr-CA' : 'en-CA'
    rec.continuous = true
    rec.interimResults = true
    rec.onspeechstart = () => {
      if (state.value === 'speaking') {
        speechSynthesis.cancel()
        send({ type: 'caller.barge_in', atMs: ms() })
        if (speakingTurn) send({ type: 'line.spoken', turnId: speakingTurn, event: 'cancelled', atMs: ms() })
        speakingTurn = null
        state.value = 'listening'
      }
    }
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]!
        const text = r[0].transcript.trim()
        if (!text) continue
        if (r.isFinal) {
          interim.value = ''
          send({ type: 'caller.text', text, final: true, language: lang.value, confidence: r[0].confidence || null, endedAtMs: ms() })
        }
        else {
          interim.value = text
          send({ type: 'caller.text', text, final: false, language: lang.value })
        }
      }
    }
    rec.onerror = (e) => { if (e.error === 'not-allowed') { state.value = 'blocked'; wantRecognition = false } }
    rec.onend = () => { rec = null; if (wantRecognition && state.value !== 'ended') setTimeout(startRecognition, 250) }
    try { rec.start() }
    catch { rec = null }
  }

  function stopRecognition() {
    wantRecognition = false
    try { rec?.abort() } catch { /* not started */ }
    rec = null
  }

  function speak(turnId: string, text: string, voiceLang: string) {
    lines.value = [...lines.value.filter(l => l.id !== turnId), { id: turnId, who: 'cv', text, final: true }]
    state.value = 'speaking'
    speakingTurn = turnId
    const done = (event: 'end' | 'cancelled') => {
      if (speakingTurn !== turnId) return
      send({ type: 'line.spoken', turnId, event, atMs: ms() })
      speakingTurn = null
      if (state.value === 'speaking') state.value = 'listening'
    }
    if (muted.value || typeof speechSynthesis === 'undefined') {
      send({ type: 'line.spoken', turnId, event: 'start', atMs: ms() })
      setTimeout(() => done('end'), Math.min(6000, 600 + text.split(/\s+/).length * 220))
      return
    }
    const u = new SpeechSynthesisUtterance(text)
    u.lang = voiceLang
    const v = speechSynthesis.getVoices().find(x => x.lang.replace('_', '-').toLowerCase() === voiceLang.toLowerCase())
    if (v) u.voice = v
    // Watchdog: some browsers never start a voice (none installed) or drop the end event on long sentences; the
    // caller's turn must still come, so the line counts as spoken after a generous reading time.
    let started = false
    const words = text.split(/\s+/).length
    const noStart = setTimeout(() => { if (!started && speakingTurn === turnId) { speechSynthesis.cancel(); send({ type: 'line.spoken', turnId, event: 'start', atMs: ms() }); setTimeout(() => done('end'), Math.min(6000, 600 + words * 220)) } }, 3000)
    const tooLong = setTimeout(() => done('end'), 4000 + words * 600)
    u.onstart = () => { started = true; clearTimeout(noStart); send({ type: 'line.spoken', turnId, event: 'start', atMs: ms() }) }
    u.onend = () => { clearTimeout(noStart); clearTimeout(tooLong); done('end') }
    u.onerror = () => { clearTimeout(noStart); clearTimeout(tooLong); done('cancelled') }
    speechSynthesis.cancel()
    speechSynthesis.speak(u)
  }

  function onMessage(m: ServerMessage) {
    switch (m.type) {
      case 'call.ready': state.value = 'listening'; stage.value = m.stage; startedAt.value = Date.now(); if (mode.value === 'browser_speech') startRecognition(); break
      case 'line.say': speak(m.turnId, m.text, m.voiceLang); break
      case 'line.stop': if (speakingTurn === m.turnId) { speechSynthesis.cancel(); speakingTurn = null; state.value = 'listening' } break
      case 'transcript.turn':
        if (m.turn.speaker === 'caller') lines.value = [...lines.value, { id: m.turn.id, who: 'caller', text: m.turn.text, final: true }]
        else if (m.turn.speaker === 'line' && !lines.value.some(l => l.id === m.turn.id)) lines.value = [...lines.value, { id: m.turn.id, who: 'cv', text: m.turn.text, final: true }]
        break
      case 'transcript.partial': interim.value = m.text; break
      case 'claim_file.slot': slip.value = [...slip.value.filter(s => s.key !== m.slot.key), m.slot]; break
      case 'call.stage': stage.value = m.stage; break
      case 'call.notice':
        notice.value = m.text
        hushed.value = m.kind === 'recording_paused' || m.kind === 'card_number_removed'
        setTimeout(() => { if (notice.value === m.text) { notice.value = null; hushed.value = false } }, 4500)
        break
      case 'call.flag': if (m.flag.kind === 'card_number_removed') hushed.value = true; break
      case 'call.ended':
        ended.value = { claimNumber: m.claimNumber, summary: m.summary, nextSteps: m.nextSteps, route: m.route ?? null }
        finish()
        break
      default: break
    }
  }

  const events: TransportEvents = {
    onMessage,
    onOpen: (t) => {
      transport = t // so the hello below reaches the line (the connect call hasn't returned yet)
      t0 = performance.now()
      send({ type: 'client.hello', mode: mode.value, language: lang.value, recognition: recognitionCtor() ? 'cloud' : 'none', voices: voices() })
    },
    onClose: (reason) => { if (state.value !== 'ended' && state.value !== 'idle' && reason !== 'hangup') state.value = 'lost' },
  }

  async function start(opts: { mode: CallMode, lang: Lang }) {
    error.value = null
    lines.value = []
    slip.value = []
    ended.value = null
    interim.value = ''
    lang.value = opts.lang
    noRecognition.value = !recognitionCtor()
    mode.value = opts.mode === 'browser_speech' && noRecognition.value ? 'typed' : opts.mode
    state.value = 'starting'
    let stream: MediaStream | null = null
    if (mode.value !== 'typed') {
      stream = await mic.start()
      if (!stream) { state.value = 'blocked'; return }
    }
    state.value = 'ringing'
    if (isMockMode()) {
      const { connectLocal } = await import('~/mock/demoLine')
      transport = connectLocal(lang.value, events)
      return
    }
    try {
      const out = await api.calls.startDemo({ mode: mode.value, language: lang.value, region: lang.value === 'fr' ? 'CA-QC' : 'CA-AB' })
      maxSeconds.value = out.connect.maxSeconds
      try { transport = await connectWebRtc(out.connect, stream, events) }
      catch { transport = await connectWebSocket(out.connect, events) }
    }
    catch (e) {
      mic.stop()
      if (e instanceof ApiError && e.code === 'line_busy') state.value = 'busy'
      else { state.value = 'lost'; error.value = e instanceof ApiError ? e.message : 'We couldn\'t reach the demo line.' }
    }
  }

  function finish() {
    stopRecognition()
    mic.stop()
    state.value = 'ended'
    setTimeout(() => transport?.close(), 7000)
  }

  function hangUp() {
    send({ type: 'caller.hangup' })
    if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
    stopRecognition()
    mic.stop()
    transport?.close()
    transport = null
    if (!ended.value) state.value = 'idle'
  }

  function sendTyped(text: string) {
    const t = text.trim()
    if (!t || !transport) return
    if (state.value === 'speaking') { speechSynthesis.cancel(); send({ type: 'caller.barge_in', atMs: ms() }) }
    send({ type: 'caller.text', text: t, final: true, language: lang.value })
  }

  function switchToTyped() {
    stopRecognition()
    mode.value = 'typed'
    send({ type: 'client.hello', mode: 'typed', language: lang.value, recognition: 'none', voices: voices() })
  }

  onBeforeUnmount(() => { if (transport) hangUp() })
  return { state, mode, lang, lines, interim, stage, slip, notice, hushed, ended, muted, error, noRecognition, startedAt, maxSeconds, micLevel: mic.level, start, hangUp, sendTyped, switchToTyped }
}
