<script setup lang="ts">
// The horizon: the whole call drawn as one mirrored waveform across the tape, Larkspur above the line and the caller
// below. The play button sits at its start (Breathe), then rides the playhead (Ride) and ripples at each new turn.
// The hushed card-number stretch is a hatched band; a tag rides the playhead while it passes. Moment labels sit
// under the line and name their time on hover.
import type { CallMoment } from '~/utils/landingCall'
import { drawConversation, themeColors, type WaveBar } from '~/utils/waveform'
import { fmtClock } from '~/utils/format'

const props = defineProps<{
  bars: WaveBar[]
  duration: number
  t: number
  playing: boolean
  turnIndex: number
  moments: CallMoment[]
  hushing: boolean
  copy: { play: string, pause: string, playLabel: string, playSub: string, paused: string, wave: string, moments: string, jump: string }
}>()
const emit = defineEmits<{ toggle: [], seek: [t: number] }>()

const canvas = ref<HTMLCanvasElement | null>(null)
const reduced = useReducedMotionPref()
const prefs = usePrefs()
const started = computed(() => props.t > 0.05 || props.playing)
const progress = computed(() => (props.duration > 0 ? props.t / props.duration : 0))
const rideAt = computed(() => (reduced.value ? 0 : progress.value))

function draw() {
  if (canvas.value) drawConversation(canvas.value, props.bars, { progress: progress.value, bar: 3, gap: 2, colors: themeColors() })
}
watch(() => [props.t, props.bars], draw)
watch(() => prefs.theme.value, () => nextTick(draw))
onMounted(() => nextTick(draw))
useResizeObserver(canvas, draw)

function seekFromEvent(e: MouseEvent) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  emit('seek', ((e.clientX - r.left) / r.width) * props.duration)
}

// Ripple: one ring per new turn while playing.
const ripples = ref<number[]>([])
let rid = 0
watch(() => props.turnIndex, (i, prev) => {
  if (!props.playing || reduced.value || i <= prev) return
  const id = ++rid
  ripples.value.push(id)
  setTimeout(() => { ripples.value = ripples.value.filter(x => x !== id) }, 800)
})

const waveLabel = computed(() => `${props.copy.wave} ${props.moments.map(m => `${m.label} ${fmtClock(m.at)}`).join(', ')}.`)
</script>

<template>
  <div class="horizon-block">
    <div class="horizon" :class="{ started }">
      <canvas ref="canvas" role="img" :aria-label="waveLabel" @click="seekFromEvent" />
      <div class="playhead" :style="{ left: `calc(var(--pl) + (100% - var(--pl) - var(--pr)) * ${rideAt})` }">
        <CvTag v-if="hushing" kind="orchid" icon="i-lucide-lock" class="hushnote">
          {{ copy.paused }}
        </CvTag>
        <button class="playbtn" type="button" :aria-label="playing ? copy.pause : copy.play" @click="emit('toggle')">
          <span class="halo" :class="{ breathe: !playing }" aria-hidden="true" />
          <span v-for="r in ripples" :key="r" class="ripple-ring" aria-hidden="true" />
          <UIcon :name="playing ? 'i-lucide-pause' : 'i-lucide-play'" class="glyph" :class="{ nudge: !playing }" />
        </button>
        <div v-if="!started" class="playlabel">
          <b>{{ copy.playLabel }}</b><span>{{ copy.playSub }}</span>
        </div>
      </div>
      <span v-if="reduced && started" class="static-cursor" :style="{ left: `calc(var(--pl) + (100% - var(--pl) - var(--pr)) * ${progress})` }" aria-hidden="true" />
    </div>
    <div class="marks" role="group" :aria-label="copy.moments">
      <UTooltip v-for="m in moments" :key="m.key" :text="`${m.label} · ${fmtClock(m.at)} · ${copy.jump}`" :content="{ side: 'bottom' }">
        <button
          type="button" class="mark" :class="{ passed: m.at <= t, hushmark: m.key === 'card' }"
          :style="{ left: `${duration > 0 ? (m.at / duration) * 100 : 0}%` }" :aria-label="`${m.label}, ${fmtClock(m.at)}`" @click="emit('seek', m.at)"
        >
          {{ m.label }}
        </button>
      </UTooltip>
    </div>
  </div>
</template>

<style scoped>
/* Full-bleed inside the tape: the wave runs from edge to edge, the play button's left edge lines up with the page's
   32 px gutter, and the right inset leaves room for the riding button at the end. */
.horizon-block { margin: 0 -32px; }
.horizon { --pl: 74px; --pr: 64px; position: relative; height: 132px; padding: 0 var(--pr) 0 var(--pl); }
.horizon canvas { width: 100%; height: 100%; display: block; cursor: pointer; }
.playhead { position: absolute; top: 0; bottom: 0; width: 0; transition: left 120ms linear; }
.started .playhead::before { content: ""; position: absolute; top: -8px; bottom: -8px; left: -1px; width: 2px; border-radius: 2px; background: var(--cv-orchid); }
.static-cursor { position: absolute; top: -8px; bottom: -8px; width: 2px; margin-left: -1px; background: var(--cv-orchid); border-radius: 2px; }
.playbtn {
  position: absolute; top: 50%; left: 0; width: 84px; height: 84px; margin: -42px 0 0 -42px; border-radius: 50%; border: 0;
  background: var(--cv-orchid); color: var(--cv-on-orchid); display: grid; place-items: center; z-index: 2;
  box-shadow: 0 14px 30px -12px color-mix(in srgb, var(--cv-orchid) 70%, transparent);
  transition: width 200ms var(--ease-voice), height 200ms var(--ease-voice), margin 200ms var(--ease-voice);
}
.playbtn:focus-visible { outline-offset: 6px; border-radius: 50%; }
.glyph { width: 30px; height: 30px; }
.glyph.nudge { margin-left: 4px; }
.started .playbtn { width: 60px; height: 60px; margin: -30px 0 0 -30px; }
.started .glyph { width: 24px; height: 24px; }
.halo { position: absolute; inset: -10px; border-radius: 50%; background: color-mix(in srgb, var(--cv-orchid) 16%, transparent); z-index: -1; }
.playlabel { position: absolute; top: 50%; left: 56px; transform: translateY(-50%); white-space: nowrap; background: var(--cv-sunk); padding: 6px 14px 6px 6px; border-radius: 6px; }
.playlabel b { display: block; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 21px; font-weight: 700; letter-spacing: -0.015em; }
.playlabel span { color: var(--cv-muted); font-size: 13.5px; font-weight: 550; }
/* Inside the wave, clear of the words written above it. */
.hushnote { position: absolute; top: 2px; left: 0; transform: translateX(-50%); z-index: 3; white-space: nowrap; animation: hush-drop var(--m-hush) var(--ease-voice) both; }
@keyframes hush-drop { from { opacity: 0; transform: translate(-50%, -8px); } }
.marks { position: relative; height: 28px; margin: 4px 64px 0 74px; }
.mark { position: absolute; top: 0; transform: translateX(-50%); border: 0; background: none; padding: 2px 4px; font-size: 12px; font-weight: 650; color: var(--cv-muted); white-space: nowrap; border-radius: 6px; }
.mark::before { content: ""; display: block; width: 5px; height: 5px; border-radius: 50%; background: currentColor; margin: 0 auto 3px; }
.mark.passed, .mark.hushmark { color: var(--cv-muted); }
.mark:hover { color: var(--cv-ink); }
@media (max-width: 720px) {
  .horizon-block { margin: 0 -16px; }
  /* Room for the play button at the start and when it rides to the end. */
  .horizon { --pl: 48px; --pr: 48px; height: 104px; }
  .playbtn { width: 64px; height: 64px; margin: -32px 0 0 -32px; }
  .playlabel { left: 42px; }
  .playlabel b { font-size: 18px; }
  .marks { display: none; }
}
</style>
