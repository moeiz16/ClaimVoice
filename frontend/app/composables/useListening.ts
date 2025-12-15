// "The line you are on": the dock's mini player. Listening survives route changes (like a music player's bar) and
// ends when you stop listening. Whisper and Take over act on that line.
import type { LiveLine } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

export interface OnLine {
  callId: string
  lineLabel: string
  callerLabel: string
  place: string | null
  language: 'en' | 'fr'
  answeredAt: string
  mode: 'listening' | 'took_over'
}

const onLine = ref<OnLine | null>(null)
const whisperOpen = ref(false)
const takeoverFor = ref<OnLine | null>(null)
const handoffFor = ref<OnLine | null>(null)
const message = ref<string | null>(null)

function fromLine(l: Pick<LiveLine, 'callId' | 'lineLabel' | 'callerLabel' | 'place' | 'language' | 'answeredAt'>, mode: OnLine['mode'] = 'listening'): OnLine {
  return { callId: l.callId, lineLabel: l.lineLabel, callerLabel: l.callerLabel, place: l.place, language: l.language, answeredAt: l.answeredAt, mode }
}

function flash(text: string) {
  message.value = text
  setTimeout(() => { if (message.value === text) message.value = null }, 4200)
}

export function useListening() {
  async function listen(l: Pick<LiveLine, 'callId' | 'lineLabel' | 'callerLabel' | 'place' | 'language' | 'answeredAt'>) {
    if (onLine.value?.callId === l.callId) return
    if (onLine.value) await stop()
    onLine.value = fromLine(l)
    try { await api.calls.listen(l.callId) }
    catch (e) {
      onLine.value = null
      flash(e instanceof ApiError && e.code === 'call_not_live' ? 'That call has just ended.' : 'We couldn\'t start listening. Try again.')
    }
  }

  async function stop() {
    const cur = onLine.value
    onLine.value = null
    whisperOpen.value = false
    if (cur) {
      try { await api.calls.stopListening(cur.callId) }
      catch { /* the call may have ended */ }
    }
  }

  async function toggle(l: Pick<LiveLine, 'callId' | 'lineLabel' | 'callerLabel' | 'place' | 'language' | 'answeredAt'>) {
    if (onLine.value?.callId === l.callId) await stop()
    else await listen(l)
  }

  async function whisper(callId: string, text: string): Promise<boolean> {
    try {
      await api.calls.whisper(callId, text)
      flash('Whispered. ClaimVoice will use it at its next turn.')
      return true
    }
    catch (e) {
      flash(e instanceof ApiError ? (e.fieldError('text') ?? e.message) : 'That note didn\'t send. Try again.')
      return false
    }
  }

  async function takeOver(target: OnLine) {
    try {
      await api.calls.takeover(target.callId)
      onLine.value = { ...target, mode: 'took_over' }
      takeoverFor.value = null
      return true
    }
    catch (e) {
      flash(e instanceof ApiError && e.code === 'already_taken' ? 'Someone else already has this call.' : 'We couldn\'t take the call. Try again.')
      return false
    }
  }

  async function giveBack(callId: string) {
    try {
      await api.calls.giveBack(callId)
      if (onLine.value?.callId === callId) onLine.value = { ...onLine.value, mode: 'listening' }
    }
    catch (e) {
      flash(e instanceof ApiError && e.code === 'not_taken_over' ? 'Take over the call first.' : 'We couldn\'t hand the call back. Try again.')
    }
  }

  async function acceptHandoff(l: OnLine) {
    try {
      await api.calls.acceptHandoff(l.callId)
      onLine.value = { ...l, mode: 'took_over' }
      return true
    }
    catch (e) {
      flash(e instanceof ApiError && e.code === 'already_taken' ? 'Someone else already took this call.' : 'We couldn\'t take the call. Try again.')
      return false
    }
  }

  return { onLine, whisperOpen, takeoverFor, handoffFor, message, listen, stop, toggle, whisper, takeOver, giveBack, acceptHandoff, fromLine, flash }
}
