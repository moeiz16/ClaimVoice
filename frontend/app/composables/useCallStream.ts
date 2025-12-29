// One live call: detail, transcript and claim file, kept current by the per-call event stream.
import type { CallDetail, LiveLine } from '~/types/api'
import { api } from '~/utils/api'
import { applyCallEvent, parseEnvelope, type CallState } from '~/utils/events'
import { apiStream, getUiLang } from '~/utils/http'
import type { StreamHandle } from '~/utils/sse'

export function useCallStream(callId: Ref<string>) {
  const state = ref<CallState>({ call: null, turns: [], file: null, partial: '', ended: null, notices: [] })
  const line = ref<LiveLine | null>(null)
  const status = ref<'loading' | 'open' | 'lost' | 'error'>('loading')
  const error = ref<string | null>(null)
  const retained = ref(true)
  const notice = ref<string | null>(null)
  let stream: StreamHandle | null = null
  let relabel: ReturnType<typeof setTimeout> | null = null

  // Event payloads carry English labels: a French view refetches the call and its claim file for French ones.
  const LABELLED = new Set(['slot.updated', 'stage.changed', 'flag.raised', 'handoff.updated', 'call.ended'])
  function relabelSoon(id: string, event: string) {
    if (getUiLang() !== 'fr' || !LABELLED.has(event)) return
    if (relabel) clearTimeout(relabel)
    relabel = setTimeout(async () => {
      relabel = null
      try {
        const [call, file] = await Promise.all([api.calls.get(id), api.calls.claimFile(id).catch(() => null)])
        if (callId.value !== id) return
        state.value = { ...state.value, call: withLineInfo(call, line.value), file: file ?? state.value.file }
      }
      catch { /* the English labels from the event stay until the next event */ }
    }, 350)
  }

  async function load(id: string) {
    status.value = 'loading'
    error.value = null
    stream?.close()
    try {
      const [call, transcript, file, live] = await Promise.all([
        api.calls.get(id),
        api.calls.transcript(id),
        api.calls.claimFile(id).catch(() => null),
        api.calls.live().catch(() => [] as LiveLine[]),
      ])
      state.value = { call: withLineInfo(call, live.find(l => l.callId === id) ?? null), turns: transcript.turns, file, partial: '', ended: null, notices: [] }
      line.value = live.find(l => l.callId === id) ?? null
      retained.value = transcript.retained
      notice.value = transcript.notice
      if (call.state !== 'ended') openStream(id)
      else status.value = 'open'
    }
    catch (e) {
      error.value = (e as Error).message
      status.value = 'error'
    }
  }

  function openStream(id: string) {
    stream = apiStream(`/calls/${encodeURIComponent(id)}/stream`, {
      onStatus: (s) => { if (s !== 'connecting') status.value = s },
      onEvent: (ev) => {
        if (ev.event === 'ping') return
        const env = parseEnvelope(ev.data)
        state.value = applyCallEvent(state.value, ev.event, env?.data ?? {})
        relabelSoon(id, ev.event)
      },
    })
  }

  watch(callId, id => id && load(id), { immediate: true })
  onBeforeUnmount(() => {
    if (relabel) clearTimeout(relabel)
    stream?.close()
  })

  return { state, line, status, error, retained, notice, reload: () => load(callId.value) }
}

/** CallDetail carries lineLabel and place in the current contract; fill them from the live line for older servers. */
export function withLineInfo(call: CallDetail, line: LiveLine | null): CallDetail {
  return { ...call, lineLabel: call.lineLabel ?? line?.lineLabel ?? null, place: call.place ?? line?.place ?? null }
}
