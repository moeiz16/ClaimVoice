<script setup lang="ts">
// The landing's hero (DESIGN.md §6): an incoming claim call you answer. Left, the call as a phone shows it (Dana in a
// sea-glass pebble, "Incoming claim call · 2:14 a.m.", a round Answer button and Read instead); once answered, a ring
// around her fills with the call and the button pauses it. Right, the conversation arrives as speech bubbles that
// inflate from their tails, the word being said darkening as it is spoken; under them, each answer is filed as a
// pebble with the moment it was heard, the card number becomes a hatched "not taken" pebble, and at the end the
// verdict turns in with its three reasons. Reduced motion: no inflating or popping; everything appears in place.
import type { CallRouteReveal, CallTurn, SlipItem } from '~/utils/landingCall'
import { reasonText } from '~/utils/landingCall'
import { routeStyle } from '~/utils/labels'
import { icon } from '~/utils/icons'
import { fmtClock } from '~/utils/format'
import { karaoke, karaokeRuns, stripCardToken } from '~/utils/transcript'

interface StageCopy {
  incoming: string
  when: string
  who: string
  about: string
  answer: string
  pause: string
  resume: string
  again: string
  read: string
  captions: string
  onCall: string
  paused: string
  ended: string
  cv: string
  caller: string
  filed: string
  filedEmpty: string
  fromPolicy: string
  notTaken: string
  removed: string
  where: string
  sample: string
  readLabel: string
}

const props = defineProps<{
  turns: CallTurn[]
  t: number
  duration: number
  playing: boolean
  items: SlipItem[]
  route: CallRouteReveal
  showRoute: boolean
  reading: boolean
  copy: StageCopy
  lang: 'en' | 'fr'
}>()
const emit = defineEmits<{ toggle: [], seek: [t: number], read: [on: boolean] }>()

const started = computed(() => props.t > 0.05 || props.playing)
const ended = computed(() => props.t >= props.duration - 0.05)
const R = 46
const C = 2 * Math.PI * R
const progress = computed(() => Math.min(1, props.t / Math.max(1, props.duration)))
const state = computed(() => (ended.value ? props.copy.ended : props.playing ? props.copy.onCall : started.value ? props.copy.paused : props.copy.incoming))
const mainLabel = computed(() => (ended.value ? props.copy.again : props.playing ? props.copy.pause : started.value ? props.copy.resume : props.copy.answer))
const mainIcon = computed(() => (ended.value ? 'i-lucide-rotate-ccw' : props.playing ? 'i-lucide-pause' : 'i-lucide-phone'))
function main() {
  if (ended.value) emit('seek', 0)
  emit('toggle')
}

// The bubbles: the turns said so far (the last four on captions), the current one karaoke.
const said = computed(() => props.turns.map((turn, i) => ({ turn, i })).filter(x => x.turn.from <= props.t))
const shown = computed(() => (props.reading ? props.turns.map((turn, i) => ({ turn, i })) : said.value.slice(-4)).map(({ turn, i }) => {
  const now = !props.reading && i === said.value[said.value.length - 1]?.i && props.t < turn.to + 0.4
  const k = karaoke(turn, props.reading ? Number.POSITIVE_INFINITY : (now ? props.t : Number.POSITIVE_INFINITY))
  return { turn, i, now, runs: karaokeRuns(k.words), hushed: k.hushed || (props.reading && turn.hush != null) }
}))
const preview = computed(() => props.turns.slice(0, 2))
const sty = computed(() => routeStyle(props.route.route))
</script>

<template>
  <section class="stage" :class="{ live: started }" :aria-label="copy.sample">
    <!-- The call, as a phone shows it -->
    <div class="phone">
      <p class="inc">
        <span class="dot" :class="{ on: playing }" aria-hidden="true" />{{ state }}
      </p>
      <div class="face" aria-hidden="true">
        <svg viewBox="0 0 100 100">
          <circle cx="50" cy="50" :r="R" class="track" />
          <circle cx="50" cy="50" :r="R" class="arc" :stroke-dasharray="`${C * progress} ${C}`" transform="rotate(-90 50 50)" />
        </svg>
        <span class="disc round">DW</span>
        <span v-if="!started" class="halo" />
      </div>
      <p class="name round">
        {{ copy.who }}
      </p>
      <p class="about">
        {{ copy.about }}
      </p>
      <p class="clock num">
        <template v-if="started">
          {{ fmtClock(t) }} / {{ fmtClock(duration) }}
        </template><template v-else>
          {{ copy.when }}
        </template>
      </p>
      <div class="btns">
        <RoundButton :icon="mainIcon" :label="mainLabel" tone="jade" size="lg" class="answer" @click="main" />
        <RoundButton :icon="reading ? 'i-lucide-captions' : 'i-lucide-text'" :label="reading ? copy.captions : copy.read" size="lg" @click="emit('read', !reading)" />
      </div>
      <p class="sample">
        {{ copy.sample }}
      </p>
    </div>

    <!-- The conversation and what gets filed -->
    <div class="talk">
      <ol class="bubbles" :class="{ reading }" :aria-label="reading ? copy.readLabel : copy.captions" :aria-hidden="reading ? undefined : 'true'">
        <template v-if="!started && !reading">
          <li v-for="(x, i) in preview" :key="`p${i}`" class="b ghost" :class="x.who">
            <small>{{ x.who === 'cv' ? copy.cv : copy.caller }}</small>
            <p :lang="lang">
              {{ stripCardToken(x.text) }}
            </p>
          </li>
        </template>
        <li v-for="x in shown" :key="x.i" class="b" :class="[x.turn.who, { now: x.now }]">
          <small>
            {{ x.turn.who === 'cv' ? copy.cv : copy.caller }}
            <button v-if="reading" type="button" class="tm num" :aria-label="`Play from ${fmtClock(x.turn.from)}`" @click="emit('seek', x.turn.from)">{{ fmtClock(x.turn.from) }}</button>
          </small>
          <p :lang="lang">
            <template v-for="(run, ri) in x.runs" :key="ri">
              <mark v-if="run.span" class="span"><template v-for="(w, wi) in run.words" :key="wi"><span class="w" :class="{ ahead: w.ahead }">{{ w.text }}</span>{{ wi < run.words.length - 1 ? ' ' : '' }}</template></mark>
              <template v-else>
                <template v-for="(w, wi) in run.words" :key="wi">
                  <span class="w" :class="{ ahead: w.ahead }">{{ w.text }}</span>{{ wi < run.words.length - 1 ? ' ' : '' }}
                </template>
              </template>{{ ri < x.runs.length - 1 ? ' ' : '' }}
            </template>
            <template v-if="x.hushed">
              {{ ' ' }}<span class="hush">■■■■ {{ copy.removed }}</span>
            </template>
          </p>
        </li>
      </ol>

      <div class="filed" :class="{ done: showRoute }">
        <p class="fh">
          <UIcon name="i-lucide-file-check" class="size-4" />{{ copy.filed }}<span v-if="items.length" class="n num">{{ items.length }}</span>
        </p>
        <TransitionGroup v-if="items.length" tag="ul" name="pebble" class="pebbles">
          <li v-for="it in items" :key="it.key">
            <span v-if="it.hushed" class="heard hushed"><UIcon name="i-lucide-lock" class="size-3.5" />{{ copy.notTaken }}</span>
            <button v-else-if="!it.fromPolicy" type="button" class="heard" :aria-label="`${it.label}, ${fmtClock(it.at)}`" @click="emit('seek', it.at)">
              <UIcon name="i-lucide-check" class="size-3.5 text-jade-ink" />{{ it.label }}<span class="at"><UIcon name="i-lucide-play" class="size-2.5" />{{ fmtClock(it.at) }}</span>
            </button>
            <span v-else class="heard plain">{{ it.label }} <small class="fp">{{ copy.fromPolicy }}</small></span>
          </li>
        </TransitionGroup>
        <p v-else class="empty">
          {{ copy.filedEmpty }}
        </p>

        <div v-if="showRoute" class="verdict" :class="`k-${sty.kind}`">
          <p class="vw round">
            <span class="vic" aria-hidden="true"><UIcon :name="icon(sty.icon)" /></span>{{ copy.where }} {{ route.label }}
          </p>
          <ol class="why">
            <li v-for="(r, i) in route.reasons" :key="i" :style="{ animationDelay: `${250 + i * 90}ms` }">
              <span class="rn num round">{{ i + 1 }}</span>{{ reasonText(r) }}
            </li>
          </ol>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.stage {
  display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 28px; padding: 26px; border-radius: 44px;
  background: linear-gradient(160deg, var(--cv-jade-wash) 0%, color-mix(in srgb, var(--cv-jade-wash) 40%, var(--cv-surface)) 55%, var(--cv-surface) 100%);
  box-shadow: var(--cv-shadow-lift);
}
/* The phone */
.phone { position: sticky; top: 16px; align-self: start; display: grid; justify-items: center; align-content: start; gap: 6px; padding: 26px 18px 20px; border-radius: 34px; background: var(--cv-surface); text-align: center; box-shadow: var(--cv-shadow-soft); }
.inc { margin: 0 0 10px; display: inline-flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 500; color: var(--cv-jade-ink); padding: 5px 13px; border-radius: 999px; background: var(--cv-jade-wash); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-jade); }
.dot.on { animation: swell 1.4s var(--ease-swell) infinite; }
.face { position: relative; width: 150px; height: 150px; display: grid; place-items: center; }
.face svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.track { fill: none; stroke: var(--cv-sunk); stroke-width: 5; }
.arc { fill: none; stroke: var(--cv-jade); stroke-width: 5; stroke-linecap: round; transition: stroke-dasharray 300ms linear; }
.disc { width: 120px; height: 120px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-sand); color: var(--cv-caller); font-size: 44px; font-weight: 900; letter-spacing: -0.02em; box-shadow: inset 0 -5px 0 var(--cv-lip); }
.halo { position: absolute; inset: 10px; border-radius: 50%; border: 3px solid var(--cv-jade); animation: halo 1.8s var(--ease-tide) infinite; pointer-events: none; }
.name { margin: 8px 0 0; font-size: 26px; font-weight: 900; letter-spacing: -0.015em; }
.about { margin: 0; color: var(--cv-muted); font-size: 14px; }
.clock { margin: 2px 0 8px; font-size: 14px; font-weight: 500; }
.btns { display: flex; gap: 22px; justify-content: center; margin-top: 6px; }
.answer :deep(.c) { width: 72px; height: 72px; font-size: 28px; }
.sample { margin: 14px 0 0; color: var(--cv-muted); font-size: 12px; }

/* The conversation */
.talk { min-width: 0; display: grid; grid-template-rows: 1fr auto; gap: 18px; }
.bubbles { list-style: none; margin: 0; padding: 4px 0 0; display: flex; flex-direction: column; justify-content: flex-end; gap: 12px; min-height: 330px; }
.bubbles.reading { justify-content: flex-start; max-height: 520px; overflow-y: auto; padding-right: 6px; }
.b { max-width: 82%; padding: 12px 18px 14px; border-radius: 24px 24px 24px 6px; background: var(--cv-surface); align-self: flex-start; animation: inflate-l var(--m-inflate) var(--ease-tide) both; transform-origin: 0 100%; box-shadow: var(--cv-shadow-soft); }
.b.caller { align-self: flex-end; border-radius: 24px 24px 6px 24px; background: var(--cv-sand); transform-origin: 100% 100%; }
.b small { display: flex; gap: 8px; align-items: baseline; font-size: 12.5px; font-weight: 600; color: var(--cv-jade-ink); margin-bottom: 2px; }
.b.caller small { color: var(--cv-caller); justify-content: flex-end; }
.b p { margin: 0; font-size: 18px; line-height: 1.45; }
.b.now p { font-family: var(--font-round); font-size: 25px; font-weight: 800; line-height: 1.28; letter-spacing: -0.01em; }
.b.ghost { opacity: .55; animation: none; box-shadow: none; }
.reading .b p { font-size: 16px; }
.w.ahead { opacity: .3; transition: opacity 160ms; }
.tm { border: 0; background: none; padding: 0; color: var(--cv-muted); font-size: 12px; font-weight: 500; }
.tm:hover { color: var(--cv-jade-ink); text-decoration: underline; }
.span { background: var(--cv-seaglass); box-shadow: none; border-radius: 8px; padding: 0 4px; }

/* What gets filed */
.filed { display: grid; gap: 10px; padding: 16px 18px; border-radius: 28px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.fh { margin: 0; display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 500; color: var(--cv-jade-ink); }
.fh .n { min-width: 24px; height: 24px; padding: 0 7px; border-radius: 999px; display: inline-grid; place-items: center; background: var(--cv-jade); color: var(--cv-on-jade); font-size: 12px; font-weight: 600; }
.pebbles { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.pebbles .heard { min-height: 32px; font-size: 13.5px; padding: 3px 5px 3px 10px; gap: 6px; }
.pebbles .heard.hushed, .pebbles .heard.plain { padding-right: 12px; }
.fp { color: var(--cv-muted); font-size: 12px; }
.empty { margin: 0; color: var(--cv-muted); font-size: 14px; }
.pebble-enter-active { animation: pop var(--m-pop) var(--ease-tide); }
.verdict { display: grid; gap: 10px; padding-top: 12px; border-top: 2px solid var(--cv-sunk); animation: turn-in var(--m-turn) var(--ease-tide) both; transform-origin: 50% 0; }
@keyframes turn-in { from { opacity: 0; transform: perspective(700px) rotateX(-40deg); } to { opacity: 1; transform: none; } }
.vw { margin: 0; display: flex; align-items: center; gap: 12px; font-size: 30px; font-weight: 900; letter-spacing: -0.02em; }
.vic { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-jade); color: var(--cv-on-jade); font-size: 22px; flex: none; }
.k-adj .vic { background: var(--cv-person); color: #fff; }
.k-siu .vic { background: var(--cv-siu); color: #fff; }
.why { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.why li { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 18px; background: var(--cv-bg); font-size: 14px; line-height: 1.4; animation: rise 300ms var(--ease-tide) both; }
.rn { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--cv-jade-wash); color: var(--cv-jade-ink); font-weight: 900; font-size: 13px; }
@media (max-width: 1000px) {
  .stage { grid-template-columns: minmax(0, 1fr); }
  .phone { position: static; }
  .why { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .stage { padding: 12px; border-radius: 30px; gap: 14px; }
  .phone { padding: 18px 12px 14px; border-radius: 26px; }
  .face { width: 116px; height: 116px; }
  .disc { width: 92px; height: 92px; font-size: 34px; }
  .name { font-size: 22px; }
  .bubbles { min-height: 0; }
  .b { max-width: 92%; padding: 10px 14px 12px; }
  .b p { font-size: 16px; }
  .b.now p { font-size: 19px; }
  .filed { padding: 14px; border-radius: 22px; }
  .vw { font-size: 24px; }
}
</style>
