<script setup lang="ts">
// The recording band (wavesurfer.js v7): two speaker lanes from precomputed peaks (ClaimVoice bars rise from the lane
// floor, the caller's hang from the lane ceiling, so together they read as one conversation), moment pins above the
// lanes, hatched card-number gaps, minute ticks, a hover time and speed pills. Keyboard while the page is open:
// Space play/pause, ←/→ 5 s, [ ] previous/next turn, J/K previous/next moment.
import WaveSurfer from 'wavesurfer.js'
import HoverPlugin from 'wavesurfer.js/dist/plugins/hover.esm.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'
import type { Moment, Recording } from '~/types/api'
import type { ExtraPin } from '~/types/ui'
import { fmtClock, fmtDurationWords } from '~/utils/format'
import { silentWavUrl } from '~/utils/audio'
import { cssVar, splitPeaks } from '~/utils/waveform'
import { layoutPins } from '~/utils/pins'


const props = withDefaults(defineProps<{
  recording: Recording
  callerLabel: string
  startAt?: number | null
  extraPins?: ExtraPin[]
  keys?: boolean
}>(), { startAt: null, extraPins: () => [], keys: true })
const emit = defineEmits<{ time: [t: number] }>()

const host = ref<HTMLElement | null>(null)
const scale = ref<HTMLElement | null>(null)
const t = ref(props.startAt ?? 0)
const playing = ref(false)
const rate = ref(1)
const ready = ref(false)
const duration = computed(() => props.recording.durationSeconds ?? 0)
const prefs = usePrefs()
let ws: WaveSurfer | null = null
let regions: RegionsPlugin | null = null
let media: HTMLAudioElement | null = null
let blobUrl: string | null = null
let clipTimer: ReturnType<typeof setTimeout> | null = null

const lanes = computed(() => splitPeaks(props.recording.peaks ?? [], duration.value, props.recording.segments, props.recording.hushes))

function laneRender(direction: 'up' | 'down') {
  return (peaks: Array<Float32Array | number[]>, ctx: CanvasRenderingContext2D) => {
    const data = peaks[0] ?? []
    const w = ctx.canvas.width
    const h = ctx.canvas.height
    const dpr = window.devicePixelRatio || 1
    const bar = 3 * dpr
    const gap = 2 * dpr
    const step = bar + gap
    const n = Math.floor(w / step)
    for (let i = 0; i < n; i++) {
      const v = Math.abs(Number(data[Math.floor((i / n) * data.length)] ?? 0))
      const hh = Math.max(1.5 * dpr, v * (h - 2 * dpr))
      const x = i * step
      const y = direction === 'up' ? h - hh : 0
      const r = Math.min(bar / 2, hh / 2)
      ctx.beginPath()
      ctx.roundRect(x, y, bar, hh, r)
      ctx.fill()
    }
  }
}

function colors() {
  return { faint: cssVar('--cv-faint'), orchid: cssVar('--cv-orchid'), caller: cssVar('--cv-caller'), muted: cssVar('--cv-muted') }
}

function channelOptions() {
  const c = colors()
  const faint = `color-mix(in srgb, ${c.faint} 45%, transparent)`
  return [
    { waveColor: faint, progressColor: c.orchid, height: 58, renderFunction: laneRender('up') },
    { waveColor: faint, progressColor: c.caller, height: 58, renderFunction: laneRender('down') },
  ]
}

function build() {
  if (!host.value || !props.recording.available || !duration.value) return
  destroy()
  media = new Audio()
  media.preload = 'metadata'
  if (props.recording.audioUrl) media.src = props.recording.audioUrl
  else { blobUrl = silentWavUrl(duration.value); media.src = blobUrl }
  regions = RegionsPlugin.create()
  const c = colors()
  ws = WaveSurfer.create({
    container: host.value,
    media,
    peaks: [lanes.value.line, lanes.value.caller],
    duration: duration.value,
    splitChannels: channelOptions(),
    normalize: false,
    interact: true,
    cursorColor: c.orchid,
    cursorWidth: 2,
    barWidth: 3,
    barGap: 2,
    barRadius: 1.5,
    dragToSeek: true,
    plugins: [
      regions,
      TimelinePlugin.create({ container: scale.value ?? undefined, height: 18, timeInterval: 60, primaryLabelInterval: 60, formatTimeCallback: s => `${Math.round(s / 60)}:00`, style: { fontSize: '11.5px', color: c.faint, fontWeight: '650' } }),
      HoverPlugin.create({ lineColor: c.muted, lineWidth: 1, labelBackground: cssVar('--cv-ink'), labelColor: cssVar('--cv-bg'), labelSize: '11px' }),
    ],
  })
  ws.on('ready', () => {
    ready.value = true
    if (props.startAt != null) ws?.setTime(props.startAt)
    addRegions()
  })
  ws.on('timeupdate', (time) => { t.value = time; emit('time', time) })
  ws.on('play', () => { playing.value = true })
  ws.on('pause', () => { playing.value = false })
  ws.on('finish', () => { playing.value = false })
}

function addRegions() {
  if (!regions) return
  regions.clearRegions()
  for (const s of props.recording.segments) regions.addRegion({ start: s.startSeconds, end: s.endSeconds, color: 'transparent', drag: false, resize: false, id: `turn-${s.turnId}` })
  for (const [a, b] of props.recording.hushes) {
    const r = regions.addRegion({ start: a, end: b, color: 'transparent', drag: false, resize: false })
    if (r.element) {
      r.element.style.background = 'repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px)'
      r.element.setAttribute('title', 'Card number removed: recording paused here')
    }
  }
  for (const m of props.recording.moments) {
    const r = regions.addRegion({ start: m.atSeconds, color: m.kind === 'sign' ? cssVar('--cv-siu') : cssVar('--cv-faint'), drag: false, resize: false })
    if (r.element) { r.element.style.width = '1.5px'; r.element.style.opacity = '0.55' }
  }
}

function destroy() {
  ws?.destroy()
  ws = null
  regions = null
  media?.pause()
  media = null
  if (blobUrl) URL.revokeObjectURL(blobUrl)
  blobUrl = null
  ready.value = false
}

watch(() => props.recording, () => nextTick(build))
watch(() => prefs.theme.value, () => nextTick(() => { ws?.setOptions({ splitChannels: channelOptions(), cursorColor: colors().orchid }) }))
watch(rate, r => ws?.setPlaybackRate(r))
onMounted(build)
onBeforeUnmount(() => { destroy(); if (clipTimer) clearTimeout(clipTimer) })

function toggle() { void ws?.playPause() }
function seek(s: number, play = false) {
  if (!ws) return
  ws.setTime(Math.max(0, Math.min(duration.value, s)))
  t.value = ws.getCurrentTime()
  if (play) void ws.play()
}
/** "Where did we hear that?": jump to the moment and play a 3-second clip. */
function playClip(s: number) {
  if (clipTimer) clearTimeout(clipTimer)
  seek(Math.max(0, s - 0.3), true)
  clipTimer = setTimeout(() => ws?.pause(), 3000)
}
defineExpose({ seek, playClip, toggle, t })

const pins = computed(() => {
  const ms = props.recording.moments.map((m: Moment) => ({ at: m.atSeconds, label: m.label, kind: m.kind === 'sign' ? 'siu' : /card/i.test(m.label) ? 'hush' : '' }))
  const extra = props.extraPins.map(p => ({ at: p.atSeconds, label: p.label, kind: p.kind === 'fail' ? 'fail' : p.kind === 'focus' ? 'focus' : 'pass' }))
  return [...ms, ...extra].sort((a, b) => a.at - b.at)
})
const pinsEl = ref<HTMLElement | null>(null)
const { width: pinsWidth } = useElementSize(pinsEl)
/** Lay pins out on up to two rows so labels never overlap, and keep them inside the band at both ends. */
const pinLayout = computed(() => layoutPins(pins.value.map(p => ({ ...p, x: duration.value ? p.at / duration.value : 0 })), pinsWidth.value || 1000))
const label = computed(() => `Recording, ${fmtDurationWords(duration.value)}. ClaimVoice above, ${props.callerLabel} below. Moments: ${pins.value.map(p => `${p.label} at ${fmtClock(p.at)}`).join(', ')}.`)

function onKey(e: KeyboardEvent) {
  if (!props.keys || !ws) return
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(el.tagName) || el.isContentEditable)) return
  const segs = props.recording.segments
  const turnNow = segs.findIndex(s => t.value >= s.startSeconds && t.value < s.endSeconds)
  if (e.key === ' ') { e.preventDefault(); toggle() }
  else if (e.key === 'ArrowRight') seek(t.value + 5)
  else if (e.key === 'ArrowLeft') seek(t.value - 5)
  else if (e.key === ']') { const n = segs.find(s => s.startSeconds > t.value + 0.1); if (n) seek(n.startSeconds) }
  else if (e.key === '[') { const p = segs[Math.max(0, turnNow - 1)]; if (p) seek(p.startSeconds) }
  else if (e.key.toLowerCase() === 'k') { const n = pins.value.find(p => p.at > t.value + 0.2); if (n) seek(n.at) }
  else if (e.key.toLowerCase() === 'j') { const p = [...pins.value].reverse().find(x => x.at < t.value - 0.2); if (p) seek(p.at) }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <section class="rec" :aria-label="label">
    <template v-if="recording.available && duration">
      <div class="ctl">
        <div class="row">
          <button class="pbtn" type="button" :aria-label="playing ? 'Pause' : `Play from ${fmtClock(t)}`" :disabled="!ready" @click="toggle">
            <CvIcon :name="playing ? 'pause' : 'play'" size="l" />
          </button>
          <time class="num">{{ fmtClock(t) }} <span>/ {{ fmtClock(duration) }}</span></time>
        </div>
        <div class="seg" role="group" aria-label="Speed">
          <button v-for="r in [1, 1.5, 2]" :key="r" type="button" :aria-pressed="rate === r" @click="rate = r">
            {{ r }}×
          </button>
        </div>
      </div>
      <div class="main">
        <div ref="pinsEl" class="pins" :class="{ two: pinLayout.some(p => p.row === 1) }" role="group" aria-label="Moments in the call">
          <button
            v-for="(p, i) in pinLayout" :key="i" type="button" :class="p.kind" :style="{ left: `${p.left}px`, top: `${p.row * 30}px` }"
            @click="seek(p.at, true)"
          >
            <CvIcon v-if="p.kind === 'siu'" name="look" size="s" />
            <CvIcon v-else-if="p.kind === 'hush'" name="lock" size="s" />
            <CvIcon v-else-if="p.kind === 'fail'" name="x" size="s" />
            <CvIcon v-else-if="p.kind === 'pass'" name="check" size="s" />
            {{ p.label }}
          </button>
        </div>
        <div class="lanes">
          <div class="labs" aria-hidden="true">
            <span><i />ClaimVoice</span>
            <span class="c"><i />{{ callerLabel }}</span>
          </div>
          <div ref="host" class="wave" />
        </div>
        <div ref="scale" class="scale num" aria-hidden="true" />
      </div>
    </template>
    <div v-else class="none">
      <span class="hatch" aria-hidden="true" />
      <p><CvIcon name="shield" size="s" />{{ recording.reason ?? 'No recording at the caller\'s request.' }} The transcript is notes only.</p>
    </div>
  </section>
</template>

<style scoped>
.rec { background: var(--cv-surface); border-radius: 28px; padding: 14px 20px 12px; display: grid; grid-template-columns: 150px 1fr; gap: 6px 16px; }
.ctl { display: flex; flex-direction: column; justify-content: center; gap: 10px; }
.ctl .row { display: flex; align-items: center; gap: 10px; }
.pbtn { width: 54px; height: 54px; border-radius: 50%; border: 0; background: var(--cv-orchid); color: var(--cv-on-orchid); display: grid; place-items: center; flex: none; }
.pbtn:focus-visible { border-radius: 50%; }
time { font-weight: 700; font-size: 14px; white-space: nowrap; }
time span { color: var(--cv-muted); font-weight: 550; }
.main { min-width: 0; padding-left: 92px; position: relative; }
.pins { position: relative; height: 30px; }
.pins.two { height: 60px; }
.pins button { position: absolute; border: 0; height: 26px; padding: 0 10px; border-radius: 999px; background: var(--cv-sunk); font-size: 12px; font-weight: 650; white-space: nowrap; display: inline-flex; align-items: center; gap: 4px; color: var(--cv-ink); }
.pins button.siu { background: var(--cv-siu-wash); color: var(--cv-siu); }
.pins button.hush { background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); color: var(--cv-muted); }
.pins button.fail { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.pins button.pass { background: var(--cv-fast-wash); color: var(--cv-fast); }
.pins button.focus { background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); }
.lanes { position: relative; margin-left: -92px; display: grid; grid-template-columns: 92px 1fr; }
.labs { display: grid; grid-template-rows: 58px 58px; }
.labs span { font-size: 12.5px; font-weight: 700; display: flex; align-items: center; gap: 6px; color: var(--cv-muted); white-space: nowrap; overflow: hidden; }
.labs i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); flex: none; }
.labs .c i { background: var(--cv-caller); }
.wave { min-width: 0; }
.scale { position: relative; height: 18px; }
.none { grid-column: 1 / -1; display: flex; align-items: center; gap: 14px; }
.hatch { width: 160px; height: 44px; border-radius: 14px; background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); flex: none; }
.none p { margin: 0; display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; }
@media (max-width: 720px) {
  .rec { grid-template-columns: 1fr; padding: 12px 14px; }
  .ctl { flex-direction: row; align-items: center; justify-content: space-between; }
  .main { padding-left: 0; }
  .lanes { margin-left: 0; grid-template-columns: 1fr; }
  .labs { display: none; }
  .pins { display: none; }
}
</style>
