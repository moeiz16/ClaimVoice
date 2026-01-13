<script setup lang="ts">
// The recorded call on the tape (wavesurfer.js v7). Two speaker lanes from precomputed peaks: ClaimVoice's bars rise
// from the centre line, the caller's hang beneath it, so together they read as one conversation. Hatched card-number
// gaps, minute ticks and a hover time sit on the wave; moment pins (with their names in a tooltip) run under it. The
// left column holds play, the time and the speed. As the recording plays, the current turn is written on the tape:
// ClaimVoice's words above the line, the caller's below, spoken words in ink and the rest of the turn waiting faintly.
// Keyboard while the page is open: Space play/pause, ←/→ 5 s, [ ] previous/next turn, J/K previous/next moment.
import WaveSurfer from 'wavesurfer.js'
import HoverPlugin from 'wavesurfer.js/dist/plugins/hover.esm.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'
import type { Moment, Recording, Turn } from '~/types/api'
import type { ExtraPin } from '~/types/ui'
import { fmtClock, fmtDurationWords } from '~/utils/format'
import { silentWavUrl } from '~/utils/audio'
import { cssVar, splitPeaks } from '~/utils/waveform'
import { layoutPins } from '~/utils/pins'
import { CARD_TOKEN, karaoke } from '~/utils/transcript'

const props = withDefaults(defineProps<{
  recording: Recording
  callerLabel: string
  startAt?: number | null
  extraPins?: ExtraPin[]
  keys?: boolean
  turns?: Turn[] | null
  label?: string
}>(), { startAt: null, extraPins: () => [], keys: true, turns: null, label: 'The recording' })
const emit = defineEmits<{ time: [t: number] }>()

const host = ref<HTMLElement | null>(null)
const scale = ref<HTMLElement | null>(null)
const t = ref(props.startAt ?? 0)
const playing = ref(false)
const rate = ref('1')
const ready = ref(false)
const duration = computed(() => props.recording.durationSeconds ?? 0)
const prefs = usePrefs()
const phone = useMediaQuery('(max-width: 720px)')
const laneHeight = computed(() => (phone.value ? 32 : 46))
let ws: WaveSurfer | null = null
let regions: RegionsPlugin | null = null
let media: HTMLAudioElement | null = null
let blobUrl: string | null = null
let clipTimer: ReturnType<typeof setTimeout> | null = null

const rates = [{ label: '1×', value: '1' }, { label: '1.5×', value: '1.5' }, { label: '2×', value: '2' }]
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
  // Played portion in full colour, unplayed at 32% of the speaker's colour (DESIGN.md §11).
  const dim = (col: string) => `color-mix(in srgb, ${col} 32%, transparent)`
  return [
    { waveColor: dim(c.orchid), progressColor: c.orchid, height: laneHeight.value, renderFunction: laneRender('up') },
    { waveColor: dim(c.caller), progressColor: c.caller, height: laneHeight.value, renderFunction: laneRender('down') },
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
      TimelinePlugin.create({ container: scale.value ?? undefined, height: 16, timeInterval: 60, primaryLabelInterval: 60, formatTimeCallback: s => `${Math.round(s / 60)}:00`, style: { fontSize: '11.5px', color: c.faint, fontWeight: '650' } }),
      HoverPlugin.create({ lineColor: c.muted, lineWidth: 1, labelBackground: cssVar('--cv-ink'), labelColor: cssVar('--cv-bg'), labelSize: '11px' }),
    ],
  })
  ws.on('ready', () => {
    ready.value = true
    ws?.setPlaybackRate(Number(rate.value))
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
watch(laneHeight, () => { ws?.setOptions({ splitChannels: channelOptions() }) })
watch(rate, r => ws?.setPlaybackRate(Number(r)))
onMounted(build)
onBeforeUnmount(() => { destroy(); if (clipTimer) clearTimeout(clipTimer) })

function toggle() { void ws?.playPause() }
function seek(s: number, play = false) {
  if (!ws) return
  ws.setTime(Math.max(0, Math.min(duration.value, s)))
  t.value = ws.getCurrentTime()
  emit('time', t.value)
  if (play) void ws.play()
}
/** "Where did we hear that?": jump to the moment and play a 3-second clip. */
function playClip(s: number) {
  if (clipTimer) clearTimeout(clipTimer)
  seek(Math.max(0, s - 0.3), true)
  clipTimer = setTimeout(() => ws?.pause(), 3000)
}
defineExpose({ seek, playClip, toggle, t, playing })

type PinKind = '' | 'siu' | 'hush' | 'fail' | 'pass' | 'focus'
const pins = computed(() => {
  const ms = props.recording.moments.map((m: Moment) => ({ at: m.atSeconds, label: m.label, kind: (m.kind === 'sign' ? 'siu' : /card/i.test(m.label) ? 'hush' : '') as PinKind }))
  const extra = props.extraPins.map(p => ({ at: p.atSeconds, label: p.label, kind: (p.kind === 'fail' ? 'fail' : p.kind === 'focus' ? 'focus' : 'pass') as PinKind }))
  return [...ms, ...extra].sort((a, b) => a.at - b.at)
})
const PIN_WORD: Record<PinKind, string> = { '': '', 'siu': 'A sign worth a closer look', 'hush': 'Recording paused', 'fail': 'Missed', 'pass': 'Met', 'focus': 'Flagged' }
const pinsEl = ref<HTMLElement | null>(null)
const { width: pinsWidth } = useElementSize(pinsEl)
/** Lay pins out on up to two rows so labels never overlap, and keep them inside the band at both ends. */
const pinLayout = computed(() => layoutPins(pins.value.map(p => ({ ...p, x: duration.value ? p.at / duration.value : 0 })), pinsWidth.value || 1000))
const ariaLabel = computed(() => `${props.label}, ${fmtDurationWords(duration.value)}. ClaimVoice above, ${props.callerLabel} below. Moments: ${pins.value.map(p => `${p.label} at ${fmtClock(p.at)}`).join(', ')}.`)

// The words on the tape: the latest turn on each side of the line, up to the playhead.
const spoken = computed(() => (props.turns ?? []).filter(x => x.speaker !== 'whisper' && x.speaker !== 'system').slice().sort((a, b) => a.atMs - b.atMs))
function lastTurn(caller: boolean): Turn | null {
  const ms = t.value * 1000 + 50
  let cur: Turn | null = null
  for (const x of spoken.value) {
    if (x.atMs > ms) break
    if ((x.speaker === 'caller') === caller) cur = x
  }
  return cur
}
const lineTurn = computed(() => lastTurn(false))
const callerTurn = computed(() => lastTurn(true))
const speaking = computed<'line' | 'caller' | null>(() => {
  const ms = t.value * 1000
  const x = spoken.value.find(s => ms >= s.atMs && ms < s.endMs + 300)
  return x ? (x.speaker === 'caller' ? 'caller' : 'line') : null
})
function words(x: Turn | null) {
  if (!x) return null
  const from = x.atMs / 1000
  const to = Math.max(from + 0.2, x.endMs / 1000)
  const hush = x.text.toLowerCase().includes(CARD_TOKEN) ? props.recording.hushes.find(([a]) => a >= from - 0.5 && a <= to)?.[0] ?? null : null
  return karaoke({ text: x.text, from, to, hush }, t.value)
}
const lineWords = computed(() => words(lineTurn.value))
const callerWords = computed(() => words(callerTurn.value))
const frOf = (x: Turn | null) => (x?.language === 'fr' ? 'fr' : undefined)

function onKey(e: KeyboardEvent) {
  if (!props.keys || !ws) return
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(el.tagName) || el.isContentEditable || el.getAttribute('role') === 'tab' || el.getAttribute('role') === 'radio')) return
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
  <Tape v-if="recording.available && duration" class="rec" :label="ariaLabel">
    <template #key>
      <div class="pk">
        <UButton
          :icon="playing ? 'i-lucide-pause' : 'i-lucide-play'" size="xl" class="play" :disabled="!ready"
          :aria-label="playing ? 'Pause' : `Play from ${fmtClock(t)}`" @click="toggle"
        />
        <time class="num">{{ fmtClock(t) }} <span>/ {{ fmtClock(duration) }}</span></time>
      </div>
      <UTabs v-model="rate" :items="rates" :content="false" variant="pill" size="xs" color="neutral" aria-label="Speed" class="speed" />
      <p class="legend" aria-hidden="true">
        <span><i />ClaimVoice above</span>
        <span class="c"><i />{{ callerLabel }} below</span>
      </p>
      <slot name="key-after" />
    </template>

    <template #above>
      <slot name="above" :t="t">
        <p v-if="lineWords && lineTurn" class="said" :class="{ quiet: speaking === 'caller' }" :lang="frOf(lineTurn)">
          <span v-for="(w, i) in lineWords.words" :key="i" :class="{ ahead: w.ahead }">{{ `${w.text} ` }}</span>
          <span v-if="lineWords.hushed" class="hush" role="img" aria-label="Card number removed">■■■■ removed</span>
          <small v-if="lineTurn.textEn" class="tr">{{ lineTurn.textEn }}</small>
        </p>
        <p v-else-if="!callerTurn" class="said hint">
          Press play to hear the call.
        </p>
      </slot>
    </template>

    <div ref="host" class="wave" />

    <template #pins>
      <div ref="scale" class="scale num" aria-hidden="true" />
      <div ref="pinsEl" class="pinrow" :class="{ two: pinLayout.some(p => p.row === 1) }" role="group" aria-label="Moments in the call">
        <UTooltip v-for="(p, i) in pinLayout" :key="i" :text="`${PIN_WORD[p.kind] ? `${PIN_WORD[p.kind]}: ` : ''}${p.label} · ${fmtClock(p.at)}`" :kbds="['J', 'K']">
          <button type="button" class="pin" :class="p.kind" :style="{ left: `${p.left}px`, top: `${p.row * 30}px` }" :aria-label="`${p.label}, ${fmtClock(p.at)}. Play from here.`" @click="seek(p.at, true)">
            <UIcon v-if="p.kind === 'siu'" name="i-lucide-search" class="size-3.5" />
            <UIcon v-else-if="p.kind === 'hush'" name="i-lucide-lock" class="size-3.5" />
            <UIcon v-else-if="p.kind === 'fail'" name="i-lucide-x" class="size-3.5" />
            <UIcon v-else-if="p.kind === 'pass'" name="i-lucide-check" class="size-3.5" />
            <UIcon v-else-if="p.kind === 'focus'" name="i-lucide-flag" class="size-3.5" />
            {{ p.label }}
          </button>
        </UTooltip>
      </div>
    </template>

    <template #below>
      <slot name="below" :t="t">
        <p v-if="callerWords && callerTurn" class="said" :class="{ quiet: speaking === 'line' }" :lang="frOf(callerTurn)">
          <span v-for="(w, i) in callerWords.words" :key="i" :class="{ ahead: w.ahead }">{{ `${w.text} ` }}</span>
          <span v-if="callerWords.hushed" class="hush" role="img" aria-label="Card number removed">■■■■ removed</span>
          <small v-if="callerTurn.textEn" class="tr">{{ callerTurn.textEn }}</small>
        </p>
      </slot>
    </template>

    <template v-if="$slots.foot" #foot>
      <slot name="foot" />
    </template>
  </Tape>

  <Tape v-else class="rec" :label="label">
    <div class="none">
      <span class="hatch" aria-hidden="true" />
      <p><UIcon name="i-lucide-shield-check" class="size-4" />{{ recording.reason ?? 'No recording at the caller\'s request.' }} The transcript is notes only.</p>
    </div>
  </Tape>
</template>

<style scoped>
.pk { display: flex; align-items: center; gap: 12px; }
.play { width: 56px; height: 56px; border-radius: 50%; justify-content: center; flex: none; }
.pk time { font-weight: 700; font-size: 14.5px; white-space: nowrap; }
.pk time span { color: var(--cv-muted); font-weight: 550; }
.speed { align-self: flex-start; }
.legend { margin: 2px 0 0; display: grid; gap: 2px; font-size: 12.5px; font-weight: 650; color: var(--cv-muted); }
.legend span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.legend i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); flex: none; }
.legend .c i { background: var(--cv-caller); }
.wave { height: 100%; min-width: 0; display: flex; flex-direction: column; justify-content: center; }
.said { margin: 0; transition: opacity 200ms; }
.said.quiet { opacity: .5; }
.said.hint { color: var(--cv-muted); }
.said .ahead { opacity: .34; transition: opacity 160ms; }
.said .tr { display: block; font-family: var(--font-sans); font-variation-settings: normal; font-size: 13.5px; font-weight: 500; letter-spacing: 0; line-height: 1.4; color: var(--cv-muted); margin-top: 2px; }
.said .hush { font-size: 13px; vertical-align: middle; }
.scale { position: relative; height: 16px; }
.pinrow { position: relative; height: 30px; margin-top: 4px; }
.pinrow.two { height: 60px; }
.pin {
  position: absolute; border: 0; height: 26px; padding: 0 10px; border-radius: 999px; background: var(--cv-surface);
  box-shadow: inset 0 0 0 1px var(--cv-rule); font-size: 12px; font-weight: 650; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 4px; color: var(--cv-ink); cursor: pointer;
}
.pin:hover { box-shadow: inset 0 0 0 1.5px var(--cv-orchid); }
.pin.siu { background: var(--cv-siu-wash); color: var(--cv-siu); box-shadow: none; }
.pin.hush { background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); color: var(--cv-muted); box-shadow: none; }
.pin.fail { background: var(--cv-urgent-wash); color: var(--cv-urgent); box-shadow: none; }
.pin.pass { background: var(--cv-fast-wash); color: var(--cv-fast); box-shadow: none; }
.pin.focus { background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); box-shadow: none; }
.none { height: 100%; display: flex; align-items: center; gap: 14px; }
.hatch { width: 160px; height: 44px; border-radius: 6px; background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-bg) 5px 10px); flex: none; }
.none p { margin: 0; display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; }
:global(.reduce-motion) .said, :global(.reduce-motion) .said .ahead { transition: none; }
@media (max-width: 1100px) {
  .legend { display: none; }
}
@media (max-width: 720px) {
  .pinrow { display: none; }
  .hatch { width: 64px; }
}
@media print {
  .rec { display: none; }
}
</style>
