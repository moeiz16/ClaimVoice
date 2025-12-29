// The line desk: GET /switchboard, then the org event stream applied through applySwitchboardEvent. Shared across
// the app (the dock's badge reads the same state), opened once while any consumer is mounted.
import type { SwitchboardSnapshot } from '~/types/api'
import { api } from '~/utils/api'
import { applySwitchboardEvent, parseEnvelope, waitingCount } from '~/utils/events'
import { apiStream, getUiLang } from '~/utils/http'
import type { StreamHandle } from '~/utils/sse'

const snapshot = ref<SwitchboardSnapshot | null>(null)
const status = ref<'idle' | 'loading' | 'open' | 'lost' | 'error'>('idle')
const error = ref<string | null>(null)
let stream: StreamHandle | null = null
let consumers = 0
let relabel: ReturnType<typeof setTimeout> | null = null

// Event payloads carry English labels; a French desk applies the event at once (codes and counts are right) and
// then refetches the snapshot for its French labels, at most once per burst of events.
const LABELLED = new Set(['line.opened', 'line.updated', 'line.closed', 'handoff.requested', 'handoff.updated', 'surge.started', 'surge.updated', 'claim.created', 'claim.routed', 'claim.updated', 'stats.updated'])
function relabelSoon(event: string) {
  if (getUiLang() !== 'fr' || !LABELLED.has(event)) return
  if (relabel) clearTimeout(relabel)
  relabel = setTimeout(() => { relabel = null; void reload() }, 350)
}

async function reload() {
  try {
    snapshot.value = await api.switchboard.snapshot()
    error.value = null
  }
  catch (e) {
    error.value = (e as Error).message
    status.value = 'error'
  }
}

async function start() {
  if (stream) return
  status.value = 'loading'
  await reload()
  if (!snapshot.value) return
  stream = apiStream('/switchboard/stream', {
    lastEventId: String(snapshot.value.lastEventId),
    onStatus: (s) => {
      if (s === 'open') status.value = 'open'
      if (s === 'lost') status.value = 'lost'
    },
    onEvent: (ev) => {
      if (ev.event === 'ping') return
      const env = parseEnvelope(ev.data)
      if (!snapshot.value) return
      const next = applySwitchboardEvent(snapshot.value, ev.event, env?.data ?? {})
      if (next === 'resync') void reload()
      else {
        snapshot.value = next
        relabelSoon(ev.event)
      }
    },
  })
}

function stop() {
  if (relabel) clearTimeout(relabel)
  relabel = null
  stream?.close()
  stream = null
  status.value = 'idle'
}

export function useSwitchboard(enabled = true) {
  onMounted(() => {
    if (!enabled) return
    consumers++
    void start()
  })
  onBeforeUnmount(() => {
    if (!enabled) return
    consumers--
    if (consumers <= 0) stop()
  })
  const waiting = computed(() => waitingCount(snapshot.value))
  return { snapshot, status, error, reload, waiting }
}
