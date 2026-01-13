<script setup lang="ts">
// The landing call's loss notice, beneath the tape: the claim as a boxed form in the seven numbered sections of the
// script, filling as the call plays. A heard value flies from its words on the tape into its box (Pluck) and the box
// rule draws orchid once (Fill); a later sentence refines a value in place; the card number never lands, its box
// Hushes into a hatched "not taken" box; when the call ends, section 8 unfurls the route with its three reasons.
// Reduced motion: nothing travels, the box and its value get a 1.6 s orchid highlight instead.
import type { CallRouteReveal, CallTurn, SlipItem } from '~/utils/landingCall'
import { NOTICE_LAYOUT, quoteFor, reasonText } from '~/utils/landingCall'
import { fmtClock } from '~/utils/format'

interface NoticeCopy {
  title: string
  empty: string
  fromPolicy: string
  pending: string
  heardAt: string
  steps: string[]
  boxes: Record<string, string>
  other: string
  states: { done: string, current: string, waiting: string, open: string }
  stepOf: string
  allDone: string
  whereTitle: string
  whereLabel: string
  wherePending: string
}

const props = defineProps<{
  items: SlipItem[]
  turns: CallTurn[]
  route: CallRouteReveal
  showRoute: boolean
  started: boolean
  animate: boolean
  copy: NoticeCopy
  lang: 'en' | 'fr'
}>()
const emit = defineEmits<{ seek: [t: number] }>()

const root = ref<HTMLElement | null>(null)
const reduced = useReducedMotionPref()
const fr = computed(() => (props.lang === 'fr' ? 'fr' : undefined))
const ended = computed(() => props.showRoute)

// Each section's width on the desktop form (four columns): 1 · 2 · 1 / 3 · 1 / 1 · 3.
const SPAN: Record<number, number> = { 1: 1, 2: 2, 3: 1, 4: 3, 5: 1, 6: 1, 7: 3 }
const STATE = {
  done: { kind: 'fast', icon: 'i-lucide-check' },
  current: { kind: 'orchid', icon: 'i-lucide-audio-lines' },
  waiting: { kind: 'plain', icon: 'i-lucide-clock' },
  open: { kind: 'plain', icon: 'i-lucide-clock' },
} as const
type State = keyof typeof STATE

const byKey = computed(() => new Map(props.items.map(i => [i.key, i])))
const sections = computed(() => {
  const known = new Set(NOTICE_LAYOUT.flatMap(s => s.boxes))
  const extra = props.items.filter(i => !known.has(i.key)).map(i => i.key)
  const list = NOTICE_LAYOUT.map((s) => {
    const keys = s.step === 4 ? [...s.boxes, ...extra] : s.boxes
    const boxes = keys.map(key => ({ key, label: props.copy.boxes[key] ?? props.copy.other, item: byKey.value.get(key) ?? null }))
    return { step: s.step, title: props.copy.steps[s.step - 1] ?? '', boxes, done: boxes.every(b => !!b.item) }
  })
  const current = props.started && !ended.value ? (list.find(s => !s.done)?.step ?? null) : null
  return list.map(s => ({ ...s, state: (s.done ? 'done' : s.step === current ? 'current' : ended.value ? 'open' : 'waiting') as State }))
})
const currentStep = computed(() => sections.value.find(s => s.state === 'current')?.step ?? null)
const stepItems = computed(() => props.copy.steps.map((title, i) => ({ title, value: i })))
const stepperValue = computed(() => (ended.value ? props.copy.steps.length - 1 : Math.max(0, (currentStep.value ?? 1) - 1)))
const stepperLabel = computed(() => (ended.value
  ? props.copy.allDone
  : `${props.copy.stepOf.replace('{n}', String(currentStep.value ?? 1))}: ${props.copy.steps[(currentStep.value ?? 1) - 1] ?? ''}`))

function stateWord(s: State) { return props.copy.states[s] }
function quote(item: SlipItem | null) { return item ? quoteFor(props.turns, item) : null }
/** Where a value's words start on the call, so pressing it plays them. */
function wordsAt(item: SlipItem): number {
  const turn = props.turns.find(t => item.at >= t.from - 0.05 && item.at <= t.to + 0.5)
  return Math.max(0, turn ? turn.from : item.at - 2)
}

// ------------------------------------------------------------ motion: Pluck, Fill, Hush, refine in place
const lit = ref<string | null>(null)
const fresh = ref<string[]>([])
function flashLit(key: string) {
  lit.value = key
  setTimeout(() => { if (lit.value === key) lit.value = null }, 1600)
}
function fill(key: string) {
  fresh.value = [...fresh.value, key]
  setTimeout(() => { fresh.value = fresh.value.filter(k => k !== key) }, 900)
}

watch(() => props.items.map(i => `${i.key}\u0001${i.label}`), async (now, before) => {
  if (!props.animate) return
  const prev = new Map((before ?? []).map((s) => { const [k, l] = s.split('\u0001'); return [k!, l!] }))
  const added: string[] = []
  const changed: string[] = []
  for (const s of now) {
    const [k, l] = s.split('\u0001') as [string, string]
    if (!prev.has(k)) added.push(k)
    else if (prev.get(k) !== l) changed.push(k)
  }
  if (!added.length && !changed.length) return
  await nextTick()
  for (const k of added) {
    const item = byKey.value.get(k)
    if (item?.hushed || item?.fromPolicy) fill(k)
    else pluck(k)
  }
  for (const k of changed) { flashLit(k); pop(k) }
})

function target(key: string) { return root.value?.querySelector<HTMLElement>(`[data-pluck="${key}"]`) ?? null }
function pop(key: string) {
  const el = target(key)
  if (el && !reduced.value && typeof el.animate === 'function') el.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.06)' }, { transform: 'scale(1)' }], { duration: 220 })
}

function pluck(key: string) {
  const el = target(key)
  const src = document.querySelector<HTMLElement>(`.lyrics .now .span[data-k="${key}"]`) ?? document.querySelector<HTMLElement>(`.lyrics .span[data-k="${key}"]`)
  if (!el) return
  if (reduced.value || !src || typeof el.animate !== 'function') {
    flashLit(key)
    fill(key)
    return
  }
  const a = src.getBoundingClientRect()
  const b = el.getBoundingClientRect()
  const ghost = document.createElement('span')
  ghost.className = 'heard'
  ghost.textContent = src.textContent
  Object.assign(ghost.style, { position: 'fixed', left: `${a.left}px`, top: `${a.top}px`, zIndex: '50', pointerEvents: 'none', background: 'var(--cv-orchid)', color: 'var(--cv-on-orchid)', boxShadow: 'var(--cv-shadow-lift)', maxWidth: '520px', whiteSpace: 'nowrap', overflow: 'hidden' })
  document.body.appendChild(ghost)
  el.style.opacity = '0'
  const dx = b.left - a.left
  const dy = b.top - a.top
  ghost.animate([
    { transform: 'translate(0,0) scale(1)' },
    { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 60}px) scale(.9)`, offset: 0.5 },
    { transform: `translate(${dx}px, ${dy}px) scale(.8)`, opacity: 0.2 },
  ], { duration: 520, easing: 'cubic-bezier(.2,.8,.2,1)' }).onfinish = () => {
    ghost.remove()
    el.style.opacity = ''
    fill(key)
    pop(key)
  }
}
</script>

<template>
  <section ref="root" class="notice" :aria-label="copy.title">
    <header class="nhead">
      <h2>{{ copy.title }}</h2>
      <span v-if="!started" class="hint">{{ copy.empty }}</span>
    </header>
    <div class="steps">
      <UStepper
        :items="stepItems" :model-value="stepperValue" disabled size="sm" color="primary" :aria-label="stepperLabel"
        :class="{ ended, idle: !started }" :ui="{ wrapper: 'max-[720px]:hidden' }"
      />
    </div>

    <div class="form">
      <fieldset v-for="sec in sections" :key="sec.step" class="sec" :class="[`st-${sec.state}`, `span-${SPAN[sec.step] ?? 1}`]">
        <legend class="sr-only-cv">
          {{ sec.step }}. {{ sec.title }}, {{ stateWord(sec.state) }}
        </legend>
        <div class="shead">
          <span class="no num" aria-hidden="true">{{ sec.step }}</span>
          <h3 aria-hidden="true">
            {{ sec.title }}
          </h3>
          <CvTag :kind="STATE[sec.state].kind" :icon="STATE[sec.state].icon" aria-hidden="true">
            {{ stateWord(sec.state) }}
          </CvTag>
        </div>
        <div class="boxes" :style="{ '--n': sec.boxes.length }">
          <div
            v-for="b in sec.boxes" :key="b.key" class="box"
            :class="{ empty: !b.item, hushed: b.item?.hushed, lit: lit === b.key, filled: fresh.includes(b.key) }"
          >
            <span class="k">{{ b.label }}</span>
            <div class="v">
              <template v-if="b.item">
                <span v-if="b.item.hushed" class="heard hushed hush-in" :data-pluck="b.key" :lang="fr">
                  <UIcon name="i-lucide-credit-card" class="size-4" />{{ b.item.label }}
                  <span class="at"><UIcon name="i-lucide-lock" class="tri" />{{ fmtClock(b.item.at) }}</span>
                </span>
                <span v-else-if="b.item.fromPolicy" class="src" :data-pluck="b.key" :lang="fr">
                  {{ b.item.label }} <small>{{ copy.fromPolicy }}</small>
                </span>
                <button
                  v-else type="button" class="heard" :class="{ lit: lit === b.key }" :data-pluck="b.key" :lang="fr"
                  :aria-label="`${b.label}: ${b.item.label}. ${copy.heardAt} ${fmtClock(b.item.at)}`" @click="emit('seek', wordsAt(b.item))"
                >
                  {{ b.item.label }}
                  <span class="at"><UIcon name="i-lucide-play" class="tri" />{{ fmtClock(b.item.at) }}</span>
                </button>
              </template>
              <span v-else class="pending">{{ copy.pending }}</span>
            </div>
            <p v-if="quote(b.item)" class="margin-note" :lang="fr">
              {{ quote(b.item) }}
            </p>
          </div>
        </div>
      </fieldset>

      <fieldset class="sec span-4 route-sec" :class="showRoute ? 'st-done' : 'st-waiting'">
        <legend class="sr-only-cv">
          8. {{ copy.whereTitle }}
        </legend>
        <div class="shead">
          <span class="no num" aria-hidden="true">8</span>
          <h3 aria-hidden="true">
            {{ copy.whereTitle }}
          </h3>
        </div>
        <div class="boxes" style="--n: 1">
          <div class="box" :class="{ empty: !showRoute }">
            <span class="k">{{ copy.whereLabel }}</span>
            <div v-if="showRoute" class="unfurl" :lang="fr">
              <RouteTag :route="route.route" :label="route.label" lg />
              <ol class="reasons">
                <li v-for="(r, i) in route.reasons" :key="i" :style="reduced ? undefined : { animationDelay: `${600 + i * 90}ms` }">
                  <b class="num">{{ i + 1 }}</b>
                  <span>{{ reasonText(r) }}</span>
                  <button
                    v-if="typeof r !== 'string' && r.atSeconds != null" type="button" class="chip num"
                    :aria-label="`${copy.heardAt} ${fmtClock(r.atSeconds)}`" @click="emit('seek', r.atSeconds)"
                  >
                    <UIcon name="i-lucide-play" class="tri" />{{ fmtClock(r.atSeconds) }}
                  </button>
                </li>
              </ol>
            </div>
            <div v-else class="v">
              <span class="pending">{{ copy.wherePending }}</span>
            </div>
          </div>
        </div>
      </fieldset>
    </div>
  </section>
</template>

<style scoped>
.notice { padding: 22px 32px 12px; display: grid; gap: 16px; }
.nhead { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
.nhead h2 { font-size: 22px; font-weight: 680; }
.hint { color: var(--cv-muted); font-size: 14px; }
.steps { padding: 2px 0 2px; overflow-x: auto; }
.steps :deep([data-state="completed"] [data-slot="indicator"]), .steps :deep(.ended [data-slot="indicator"]) { background: var(--cv-fast); color: #fff; }
.steps :deep(.idle [data-state="active"] [data-slot="indicator"]) { background: var(--cv-sunk-2); color: var(--cv-ink); }

/* The form: four columns on the desktop; sections span by how many boxes they hold. */
.form { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px 16px; align-items: start; }
.span-1 { grid-column: span 1; } .span-2 { grid-column: span 2; } .span-3 { grid-column: span 3; } .span-4 { grid-column: 1 / -1; }
.sec { border: 0; margin: 0; padding: 0; min-width: 0; }
.shead { display: flex; align-items: center; gap: 10px; padding: 0 0 8px; min-width: 0; }
.no {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 15px;
  background: var(--cv-ink); color: var(--cv-bg); transition: background-color 200ms, color 200ms;
}
.st-current .no { background: var(--cv-orchid); color: var(--cv-on-orchid); }
.st-waiting .no, .st-open .no { background: var(--cv-sunk-2); color: var(--cv-ink); }
.st-done .no { background: var(--cv-fast); color: #fff; }
.shead h3 { font-size: 17px; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.shead :deep(.cv-tag) { margin-left: auto; flex: none; }
.boxes {
  display: grid; grid-template-columns: repeat(var(--n, 1), minmax(0, 1fr)); background: var(--cv-surface);
  border-top: 1px solid var(--cv-rule); border-left: 1px solid var(--cv-rule); border-radius: 6px; overflow: hidden;
}
.st-current .boxes { box-shadow: 0 0 0 2px var(--cv-orchid-wash); }
.box {
  border-right: 1px solid var(--cv-rule); border-bottom: 1px solid var(--cv-rule); padding: 9px 12px 11px;
  display: flex; flex-direction: column; gap: 5px; min-width: 0; min-height: 84px; transition: background-color 160ms;
}
.box.empty { background: repeating-linear-gradient(-45deg, transparent 0 9px, color-mix(in srgb, var(--cv-sunk) 70%, transparent) 9px 10px); }
.box.lit { background: var(--cv-orchid-wash); }
.box.hushed { background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); }
.k { font-size: 12px; font-weight: 650; color: var(--cv-muted); transition: transform 200ms var(--ease-voice); }
.box.filled .k { transform: translateY(-2px); }
.v { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-height: 32px; }
.v .heard { max-width: 100%; }
.heard .tri { width: 10px; height: 10px; }
.box.hushed .heard.hushed { background: var(--cv-surface); }
.hush-in { animation: hush-collapse var(--m-hush) var(--ease-voice) both; overflow: hidden; }
@keyframes hush-collapse { from { filter: blur(4px); max-width: 2em; opacity: .4; } to { filter: blur(0); max-width: 24em; opacity: 1; } }
.src { font-size: 14.5px; font-weight: 600; display: inline-flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
.src small { color: var(--cv-muted); font-weight: 550; font-size: 12px; }
.margin-note { margin: 0; }

/* Section 8: the route unfurls from the left (Route), its reasons follow 90 ms apart. */
.unfurl { display: flex; align-items: center; gap: 12px 20px; flex-wrap: wrap; padding: 4px 0 2px; animation: unfurl var(--m-route) var(--ease-voice) both; }
@keyframes unfurl { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
.reasons { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 0; padding: 0; list-style: none; font-size: 14.5px; font-weight: 550; }
.reasons li { display: inline-flex; align-items: center; gap: 8px; animation: rise-in 300ms var(--ease-voice) both; }
.reasons b {
  width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; flex: none; font-size: 12.5px; font-weight: 750;
  background: var(--cv-fast-wash); color: var(--cv-fast);
}
.chip {
  display: inline-flex; align-items: center; gap: 3px; height: 22px; padding: 0 8px 0 6px; border-radius: 999px; border: 0;
  background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); font-size: 12px; font-weight: 650;
}
.chip .tri { width: 10px; height: 10px; }

@media (max-width: 1180px) {
  .form { grid-template-columns: minmax(0, 1fr); }
  .span-1, .span-2, .span-3 { grid-column: 1 / -1; }
}
@media (max-width: 720px) {
  .notice { padding: 18px 16px 8px; }
  .boxes { grid-template-columns: minmax(0, 1fr); }
  .box { min-height: 0; }
  .reasons { flex-direction: column; gap: 8px; }
  .reasons li { align-items: flex-start; }
}
</style>
