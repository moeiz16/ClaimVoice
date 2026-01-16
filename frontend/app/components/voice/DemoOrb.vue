<script setup lang="ts">
// The demo-line pebble: one round object, three states, sitting in the phone card. Idle swells softly; listening scales with the microphone level through a
// spring (stiffness 300, damping 30); speaking pulses with ClaimVoice's turn. Reduced motion: a static ring with a
// five-step level meter updated four times a second.
import { levelStep } from '~/utils/waveform'

const props = withDefaults(defineProps<{ state?: 'idle' | 'ringing' | 'listening' | 'speaking' | 'ended', level?: number, size?: number, typed?: boolean }>(), { state: 'idle', level: 0, size: 176, typed: false })
const reduced = useReducedMotionPref()
const scale = ref(1)
let v = 0
let raf = 0
let last = 0

const target = computed(() => {
  if (props.state === 'listening') return 1 + props.level * 0.12
  if (props.state === 'speaking') return 1 + 0.05 + 0.04 * Math.sin(performance.now() / 160)
  return 1
})

function step(ts: number) {
  raf = requestAnimationFrame(step)
  const dt = Math.min(0.05, last ? (ts - last) / 1000 : 0.016)
  last = ts
  const x = scale.value
  const a = -300 * (x - target.value) - 30 * v
  v += a * dt
  scale.value = x + v * dt
}
onMounted(() => { raf = requestAnimationFrame(step) })
onBeforeUnmount(() => cancelAnimationFrame(raf))

const steps = ref(0)
let meterTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => { meterTimer = setInterval(() => { steps.value = levelStep(props.level) }, 250) })
onBeforeUnmount(() => { if (meterTimer) clearInterval(meterTimer) })
const live = computed(() => props.state === 'listening' || props.state === 'speaking')
const glyph = computed(() => { const px = `${Math.round(Math.max(20, props.size * 0.2))}px`; return { width: px, height: px } })
</script>

<template>
  <div class="orb" :class="[state, { reduced }]" :style="{ width: `${size}px`, height: `${size}px` }">
    <span class="ring2" :class="{ swell: !live && !reduced }" aria-hidden="true" />
    <span class="core" :class="{ swell: state === 'idle' && !reduced }" :style="!reduced && live ? { transform: `scale(${scale})` } : undefined">
      <UIcon v-if="state === 'listening' && typed" name="i-lucide-keyboard" :style="glyph" />
      <UIcon v-else-if="state === 'listening'" name="i-lucide-mic" :style="glyph" />
      <UIcon v-else name="i-lucide-phone" :style="glyph" />
    </span>
    <span v-if="state === 'ringing' && !reduced" class="ringwave" aria-hidden="true" />
    <span v-if="reduced && live" class="meter" aria-hidden="true">
      <i v-for="n in 5" :key="n" :class="{ on: n <= steps }" />
    </span>
  </div>
</template>

<style scoped>
.orb { position: relative; display: grid; place-items: center; }
.core { width: 100%; height: 100%; border-radius: 50%; display: grid; place-items: center; color: var(--cv-on-jade); background: var(--cv-jade); box-shadow: inset 0 -7px 0 var(--cv-lip); will-change: transform; }
.listening .core { background: var(--cv-caller); color: var(--cv-sand); }
.ended .core { background: var(--cv-sunk-2); color: var(--cv-muted); box-shadow: none; }
.ring2 { position: absolute; inset: -14px; border-radius: 50%; border: 3px solid var(--cv-seaglass); }
.swell { animation: swell 3.2s var(--ease-swell) infinite; }
.ringwave { position: absolute; inset: 0; border-radius: 50%; border: 3px solid var(--cv-jade); animation: halo 600ms var(--ease-tide) 2; }
.meter { position: absolute; bottom: -30px; display: flex; gap: 4px; }
.meter i { width: 14px; height: 6px; border-radius: 3px; background: var(--cv-sunk-2); }
.meter i.on { background: var(--cv-jade); }
</style>
