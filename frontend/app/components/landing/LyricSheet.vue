<script setup lang="ts">
// The lyric sheet: the current turn large (44 px), the two before it small and faded. ClaimVoice's lines hug the
// left, the caller's hug the right. Words arrive karaoke-style; a heard phrase gets the orchid wash once said; the
// card digits collapse into a hatched "■■■■ removed" pill (Hush).
import type { CallTurn } from '~/utils/landingCall'
import { karaoke, karaokeRuns } from '~/utils/transcript'

const props = defineProps<{ turns: CallTurn[], t: number, names: { cv: string, caller: string }, removed: string }>()

const idx = computed(() => {
  let i = -1
  props.turns.forEach((x, j) => { if (x.from <= props.t) i = j })
  return i
})
const shown = computed(() => {
  const i = idx.value
  if (i < 0) return []
  return props.turns.slice(Math.max(0, i - 2), i + 1).map((turn, j, arr) => {
    const now = j === arr.length - 1
    const k = karaoke(turn, now ? props.t : Number.POSITIVE_INFINITY)
    return { turn, now, runs: karaokeRuns(k.words), hushed: k.hushed, key: props.turns.indexOf(turn) }
  })
})
</script>

<template>
  <TransitionGroup tag="div" name="lyric" class="lines" aria-hidden="true">
    <div v-for="l in shown" :key="l.key" class="line" :class="[l.turn.who, l.now ? 'now' : 'past']">
      <div class="who">
        <i />{{ l.turn.who === 'cv' ? names.cv : names.caller }}
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
.lines { position: absolute; inset: auto 0 18px 0; display: flex; flex-direction: column; gap: 14px; }
.line { max-width: 66%; transition: transform 420ms var(--ease-voice), opacity 420ms var(--ease-voice); }
.line.caller { align-self: flex-end; text-align: right; }
.who { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 700; color: var(--cv-muted); margin-bottom: 4px; }
.who i { width: 9px; height: 9px; border-radius: 50%; background: var(--cv-orchid); display: inline-block; }
.caller .who i { background: var(--cv-caller); }
p { margin: 0; font-family: var(--font-display); font-variation-settings: "opsz" 72; letter-spacing: -0.025em; }
.past p { font-size: calc(21px * var(--cv-caption-scale)); font-weight: 500; line-height: 1.3; color: var(--cv-faint); }
.past .who { display: none; }
.now p { font-size: calc(44px * var(--cv-caption-scale)); font-weight: 700; line-height: 1.12; }
.cv.now p { color: var(--cv-ink); }
.caller.now p { color: var(--cv-caller); }
.w.ahead { color: var(--cv-faint); opacity: .55; }
.past .span { box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--cv-orchid) 50%, transparent); background: none; }
.now .span { padding: 0 6px; border-radius: 12px; animation: wash-in 180ms var(--ease-voice) both; }
@keyframes wash-in { from { clip-path: inset(0 100% 0 0 round 12px); } to { clip-path: inset(0 0 0 0 round 12px); } }
.now .hush { font-size: 18px; height: 40px; padding: 0 16px; vertical-align: 8px; }
.hush-in { animation: hush-collapse var(--m-hush) var(--ease-voice) both; overflow: hidden; }
@keyframes hush-collapse { from { filter: blur(4px); max-width: 1em; opacity: .4; } to { filter: blur(0); max-width: 14em; opacity: 1; } }
.lyric-enter-from { opacity: 0; transform: translateY(18px); }
.lyric-leave-active { position: absolute; opacity: 0; }
@media (max-width: 720px) {
  .line { max-width: 88%; }
  .now p { font-size: calc(28px * var(--cv-caption-scale)); }
  .past p { font-size: 16px; }
  .now .hush { font-size: 13px; height: 28px; vertical-align: 3px; }
}
</style>
