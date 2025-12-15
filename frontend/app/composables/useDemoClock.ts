// Demo time for the UI: the server's X-ClaimVoice-Now (kept as an offset in utils/demoClock.ts), ticking. Every
// displayed "now", elapsed call time and waiting time goes through this, never the raw browser clock.
import { demoNow } from '~/utils/demoClock'
import { fmtClock, secondsSince } from '~/utils/format'

const tick = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
let users = 0

export function useDemoClock(intervalMs = 1000) {
  const now = computed(() => { void tick.value; return demoNow() })
  onMounted(() => {
    users++
    if (!timer) timer = setInterval(() => { tick.value++ }, intervalMs)
  })
  onBeforeUnmount(() => {
    users--
    if (users <= 0 && timer) { clearInterval(timer); timer = null }
  })
  /** Seconds since an ISO instant, in demo time (reactive). */
  const since = (iso: string | null | undefined) => secondsSince(iso, now.value)
  /** "3:12" since an ISO instant (reactive). */
  const elapsed = (iso: string | null | undefined) => fmtClock(since(iso))
  return { now, since, elapsed }
}
