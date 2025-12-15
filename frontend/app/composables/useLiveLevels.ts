// Live waveform bars for a line. Browser calls carry no server audio, so the levels are drawn from turn timing:
// whoever is speaking now (from the call's turns, the per-call partial caption, or a default rhythm) drives a
// speech-like level. One bar every 90 ms into a ring buffer; paused when off-screen or when the tab is hidden.
import { useDocumentVisibility, useIntersectionObserver } from '@vueuse/core'
import { defaultRhythm, LiveBars, rng, seedOf, syntheticLevel, type WaveBar, type Who } from '~/utils/waveform'

export interface LevelSource {
  /** Who is speaking at time t (seconds since start), or null to use the default rhythm. */
  who?: (t: number) => Who | null
  /** A real analyser level, 0..1 (microphone or speech output), when one exists. */
  level?: () => { who: Who, level: number } | null
}

export function useLiveLevels(target: Ref<HTMLElement | null | undefined>, seedKey: Ref<string> | string, source: LevelSource = {}, size = 120) {
  const buffer = new LiveBars(size)
  const version = ref(0)
  const reduced = useReducedMotionPref()
  const visible = ref(true)
  const docVisible = useDocumentVisibility()
  useIntersectionObserver(target, ([entry]) => { visible.value = !!entry?.isIntersecting })

  const seed = computed(() => seedOf(typeof seedKey === 'string' ? seedKey : seedKey.value))
  let r = rng(seed.value)
  let rhythm = defaultRhythm(seed.value)
  watch(seed, (s) => { r = rng(s); rhythm = defaultRhythm(s) })

  let t = 0
  const sample = (): WaveBar => {
    const real = source.level?.()
    if (real) return { who: real.who, a: Math.max(0.04, real.level) }
    const who = source.who?.(t) ?? rhythm(t)
    return { who, a: syntheticLevel(who, t, r) }
  }

  // Pre-fill so the strip never starts flat.
  for (let i = 0; i < size; i++) { buffer.push(sample()); t += 0.09 }

  let raf = 0
  let last = 0
  const loop = (ts: number) => {
    raf = requestAnimationFrame(loop)
    if (!visible.value || docVisible.value === 'hidden') return
    if (ts - last < (reduced.value ? 250 : 90)) return
    last = ts
    buffer.push(sample())
    t += 0.09
    version.value++
  }
  onMounted(() => { raf = requestAnimationFrame(loop) })
  onBeforeUnmount(() => cancelAnimationFrame(raf))

  /** The newest level (for meters). */
  const current = computed(() => { void version.value; return buffer.bars[buffer.bars.length - 1] ?? { who: 'gap' as Who, a: 0 } })

  return { buffer, version, current }
}
