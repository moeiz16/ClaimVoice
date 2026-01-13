<script setup lang="ts">
// The words on the tape, one side at a time: Larkspur's side above the line, the caller's below it. Each side shows
// its current line large and the line before it small and faded, furthest from the line. Words arrive karaoke-style
// (spoken in ink, the rest faint); a heard phrase gets the orchid wash once said (Pluck flies from it); the card
// digits collapse into a hatched "■■■■ removed" pill (Hush). The side that isn't speaking rests, dimmed.
import type { CallTurn } from '~/utils/landingCall'
import { karaoke, karaokeRuns } from '~/utils/transcript'

const props = defineProps<{ turns: CallTurn[], t: number, side: 'cv' | 'caller', name: string, removed: string, lang?: string }>()

const idx = computed(() => {
  let i = -1
  props.turns.forEach((x, j) => { if (x.from <= props.t) i = j })
  return i
})
const speaking = computed(() => {
  const now = props.turns[idx.value]
  return !!now && now.who === props.side
})
const shown = computed(() => {
  const mine: { turn: CallTurn, i: number }[] = []
  props.turns.forEach((turn, i) => { if (turn.who === props.side && turn.from <= props.t) mine.push({ turn, i }) })
  return mine.slice(-2).map(({ turn, i }, j, arr) => {
    const now = j === arr.length - 1
    const k = karaoke(turn, now ? props.t : Number.POSITIVE_INFINITY)
    return { turn, now, runs: karaokeRuns(k.words), hushed: k.hushed, key: i }
  })
})
</script>

<template>
  <TransitionGroup tag="div" name="lyric" class="lyrics" :class="[side, { resting: !speaking }]" aria-hidden="true">
    <div v-for="l in shown" :key="l.key" class="line" :class="l.now ? 'now' : 'past'" :lang="lang">
      <div v-if="l.now" class="who">
        <i />{{ name }}
      </div>
      <p>
        <template v-for="(run, ri) in l.runs" :key="ri">
          <mark v-if="run.span" class="span" :data-k="run.span"><template v-for="(w, wi) in run.words" :key="wi"><span class="w" :class="{ ahead: w.ahead }">{{ w.text }}</span>{{ wi < run.words.length - 1 ? ' ' : '' }}</template></mark>
          <template v-else>
            <template v-for="(w, wi) in run.words" :key="wi">
              <span class="w" :class="{ ahead: w.ahead }">{{ w.text }}</span>{{ wi < run.words.length - 1 ? ' ' : '' }}
            </template>
          </template>{{ ri < l.runs.length - 1 ? ' ' : '' }}
        </template>
        <template v-if="l.hushed">
          {{ ' ' }}<span class="hush hush-in">■■■■ {{ removed }}</span>
        </template>
      </p>
    </div>
  </TransitionGroup>
</template>

<style scoped>
/* Above the line the newest words sit at the bottom, nearest the wave; below the line, at the top. */
.lyrics { position: relative; display: flex; gap: 8px; height: 100%; overflow: hidden; }
.lyrics.cv { flex-direction: column; justify-content: flex-end; mask-image: linear-gradient(to bottom, transparent 0, #000 28px); }
.lyrics.caller { flex-direction: column-reverse; justify-content: flex-end; align-items: flex-end; text-align: right; mask-image: linear-gradient(to top, transparent 0, #000 28px); }
.line { max-width: min(72%, 1000px); transition: opacity 420ms var(--ease-voice); }
.caller .line { max-width: min(66%, 860px); }
.who { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 650; color: var(--cv-muted); margin-bottom: 2px; }
.who i { width: 9px; height: 9px; border-radius: 50%; background: var(--cv-orchid); display: inline-block; }
.caller .who i { background: var(--cv-caller); }
p { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; letter-spacing: -0.015em; }
.past p { font-size: calc(18px * var(--cv-caption-scale)); font-weight: 500; line-height: 1.3; color: var(--cv-muted); }
.now p { font-size: calc(36px * var(--cv-caption-scale)); font-weight: 640; line-height: 1.14; }
.cv .now p { color: var(--cv-ink); }
.caller .now p { color: var(--cv-caller); }
.resting .now { opacity: .55; }
.w.ahead { color: var(--cv-faint); opacity: .55; }
.past .span { box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--cv-orchid) 50%, transparent); background: none; }
.now .span { padding: 0 6px; animation: wash-in 180ms var(--ease-voice) both; }
@keyframes wash-in { from { clip-path: inset(0 100% 0 0 round 6px); } to { clip-path: inset(0 0 0 0 round 6px); } }
.now .hush { font-size: 16px; height: 36px; padding: 0 14px; vertical-align: 6px; }
.hush-in { animation: hush-collapse var(--m-hush) var(--ease-voice) both; overflow: hidden; }
@keyframes hush-collapse { from { filter: blur(4px); max-width: 1em; opacity: .4; } to { filter: blur(0); max-width: 14em; opacity: 1; } }
.lyric-enter-from { opacity: 0; transform: translateY(12px); }
.caller .lyric-enter-from { transform: translateY(-12px); }
.lyric-enter-active { transition: opacity 320ms var(--ease-voice), transform 320ms var(--ease-voice); }
.lyric-leave-active { display: none; }
@media (max-width: 720px) {
  .line, .caller .line { max-width: 92%; }
  .now p { font-size: calc(22px * var(--cv-caption-scale)); }
  .past p { font-size: 14.5px; }
  .now .hush { font-size: 12.5px; height: 26px; vertical-align: 2px; }
}
</style>
