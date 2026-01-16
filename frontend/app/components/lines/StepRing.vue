<script setup lang="ts">
// A ring around a caller's initials (DESIGN.md §3, "Ring"). Steps: the script's seven steps as arcs, done ones jade,
// the current one half drawn. Wait: one arc that fills as a waiting caller's wait grows (a full ring at `of` seconds).
// The words travel with it: the ring is an image with an accessible name, never colour alone.
import type { StageInfo } from '~/types/api'

const props = withDefaults(defineProps<{
  label: string
  initials: string
  stage?: StageInfo | null
  waitSeconds?: number | null
  of?: number
  size?: number
  tone?: 'jade' | 'siu' | 'urgent' | 'person' | 'plain'
}>(), { stage: null, waitSeconds: null, of: 300, size: 64, tone: 'jade' })

const R = 44
const C = 2 * Math.PI * R
const GAP = 5
const arcs = computed(() => {
  const n = props.stage?.steps ?? 7
  const seg = C / n
  return Array.from({ length: n }, (_, i) => {
    const step = i + 1
    const cur = props.stage?.step ?? 0
    const fill = step < cur ? 1 : step === cur ? 0.5 : 0
    return { i, len: seg - GAP, offset: -i * seg, fill }
  })
})
const waitFrac = computed(() => Math.min(1, Math.max(0.04, (props.waitSeconds ?? 0) / props.of)))
const aria = computed(() => (props.stage ? `${props.label}: step ${props.stage.step} of ${props.stage.steps}, ${props.stage.stepLabel}` : props.label))
</script>

<template>
  <span class="sring" :class="`t-${tone}`" :style="{ width: `${size}px`, height: `${size}px` }" role="img" :aria-label="aria">
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <g transform="rotate(-90 50 50)">
        <template v-if="stage">
          <circle
            v-for="a in arcs" :key="a.i" cx="50" cy="50" :r="R" fill="none" class="track"
            :stroke-dasharray="`${a.len} ${C}`" :stroke-dashoffset="a.offset"
          />
          <circle
            v-for="a in arcs.filter(x => x.fill)" :key="`f${a.i}`" cx="50" cy="50" :r="R" fill="none" class="arc"
            :stroke-dasharray="`${a.len * a.fill} ${C}`" :stroke-dashoffset="a.offset"
          />
        </template>
        <template v-else>
          <circle cx="50" cy="50" :r="R" fill="none" class="track" />
          <circle cx="50" cy="50" :r="R" fill="none" class="arc draw" :stroke-dasharray="`${C * waitFrac} ${C}`" />
        </template>
      </g>
    </svg>
    <span class="ini" :style="{ fontSize: `${Math.round(size * 0.3)}px` }">{{ initials }}</span>
    <slot />
  </span>
</template>

<style scoped>
.sring { position: relative; display: inline-grid; place-items: center; flex: none; }
svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.track { stroke: var(--cv-sunk-2); stroke-width: 7; stroke-linecap: round; }
.arc { stroke: var(--cv-jade); stroke-width: 7; stroke-linecap: round; transition: stroke-dasharray var(--m-ring) var(--ease-tide); }
.t-siu .arc { stroke: var(--cv-siu); }
.t-urgent .arc { stroke: var(--cv-urgent); }
.t-person .arc { stroke: var(--cv-person); }
.t-plain .arc { stroke: var(--cv-faint); }
.ini {
  position: relative; width: 74%; height: 74%; border-radius: 50%; display: grid; place-items: center;
  font-family: var(--font-round); font-weight: 900; letter-spacing: -0.02em; background: var(--cv-sand); color: var(--cv-caller);
}
.draw { animation: ring-draw var(--m-ring) var(--ease-tide); }
@keyframes ring-draw { from { stroke-dasharray: 0 999; } }
</style>
