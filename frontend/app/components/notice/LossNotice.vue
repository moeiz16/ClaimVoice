<script setup lang="ts">
// The loss notice (DESIGN.md §0.2): the claim as a boxed form whose numbered sections are the seven script steps.
// The stepper above it is the same seven steps (Nuxt UI Stepper, display only). Each box: its label in the corner,
// the value with its source (a heard pill with ▸ time, "from the policy", or a dashed "Not heard yet"), and a margin
// note with the caller's own words. Slots: `before` (e.g. Remarks / In short), `step-N` (extra content inside a
// section, e.g. photos in 5), `after` (e.g. section 8, where the claim goes).
import type { Lang, Slot, Turn } from '~/types/api'
import { linkKey } from '~/composables/useHeardLinks'
import { boxWidth, marginNote, STEPS, stepperIndex } from '~/utils/notice'
import type { NoticeSection } from '~/utils/notice'

const props = withDefaults(defineProps<{
  sections: NoticeSection[]
  step: number
  ended?: boolean
  turns?: Pick<Turn, 'id' | 'text'>[] | null
  language?: Lang
  /** Words for the notice's own labels: staff screens stay in English; the caller's demo line can be French. */
  words?: Lang
  stepper?: boolean
  loading?: boolean
  title?: string
  reference?: string | null
}>(), { ended: false, turns: null, language: 'en', words: 'en', stepper: true, loading: false, title: 'Loss notice', reference: null })

const emit = defineEmits<{ activate: [slot: Slot], hover: [slot: Slot | null] }>()
const links = useHeardLinks()
const isLinked = (s: Slot) => !!s.span && (links.active.value === linkKey(s.span) || links.flashKey.value === linkKey(s.span))
const fr = computed(() => (props.language === 'fr' ? 'fr' : undefined))
const STEPS_FR = ['Consentement', 'Contrat', 'Sécurité', 'Ce qui s\'est passé', 'Photos', 'Couverture', 'Relecture']
const stepNames = computed(() => (props.words === 'fr' ? STEPS_FR : [...STEPS]))
const stepItems = computed(() => stepNames.value.map((title, i) => ({ title, value: i, icon: undefined as string | undefined })))
const active = computed(() => stepperIndex(props.step, props.ended))
// Fill: a box whose first value arrives while you watch draws its rule orchid once. Values already there when the
// notice opens don't animate.
const filledOnce = new Set<string>()
const ready = ref(false)
onMounted(() => { setTimeout(() => { ready.value = true }, 800) })
function freshlyFilled(s: Slot): boolean {
  if (!s.display || filledOnce.has(s.key)) return false
  filledOnce.add(s.key)
  return ready.value
}
const STATE = {
  done: { kind: 'fast', icon: 'check', word: 'Complete' },
  current: { kind: 'orchid', icon: 'waves', word: 'Filling in' },
  open: { kind: 'plain', icon: 'clock', word: 'Still open' },
  waiting: { kind: 'plain', icon: 'clock', word: 'Not reached yet' },
} as const
const STATE_FR = { done: 'Complet', current: 'En cours', open: 'Encore ouvert', waiting: 'Pas encore atteint' } as const
function stateWord(sec: { key: string, state: keyof typeof STATE }): string {
  const verified = sec.key.startsWith('caller') && sec.state === 'done'
  if (props.words === 'fr') return verified ? 'Vérifié' : STATE_FR[sec.state]
  return verified ? 'Verified' : STATE[sec.state].word
}
</script>

<template>
  <section class="notice" :aria-label="title">
    <header class="nhead">
      <h2>{{ title }}</h2>
      <span v-if="reference" class="ref num">{{ reference }}</span>
      <slot name="head" />
    </header>
    <div v-if="stepper" class="steps">
      <UStepper
        :items="stepItems" :model-value="Math.min(active, STEPS.length - 1)" disabled size="sm" color="primary"
        :aria-label="words === 'fr' ? (ended ? 'Toutes les étapes sont faites' : `Étape ${step} sur 7 : ${stepNames[active] ?? ''}`) : (ended ? 'Every step of the call is done' : `Step ${step} of 7: ${stepNames[active] ?? ''}`)"
        :class="{ ended }" :ui="{ wrapper: 'max-[720px]:hidden' }"
      />
    </div>
    <slot name="before" />
    <div v-if="loading" class="sec" aria-busy="true">
      <div class="boxes">
        <div v-for="n in 8" :key="n" class="box w1">
          <USkeleton class="h-3 w-1/2" /><USkeleton class="h-7 w-4/5 mt-2" />
        </div>
      </div>
    </div>
    <fieldset v-for="sec in sections" v-else :key="sec.key" class="sec" :class="`st-${sec.state}`">
      <legend class="sr-only-cv">{{ sec.step }}. {{ sec.title }}</legend>
      <div class="shead" aria-hidden="false">
        <span class="no num" aria-hidden="true">{{ sec.step }}</span>
        <h3>{{ sec.title }}</h3>
        <CvTag :kind="STATE[sec.state].kind" :icon="STATE[sec.state].icon">{{ stateWord(sec) }}</CvTag>
      </div>
      <div class="boxes">
        <div v-for="s in sec.slots" :key="s.key" class="box" :class="[`w${boxWidth(s)}`, { linked: isLinked(s), empty: !s.display, filled: freshlyFilled(s) }]">
          <span class="k">{{ s.label }}</span>
          <div class="v">
            <HeardValue :field="s" :linked="isLinked(s)" :lang="fr" @hover="on => { links.hover(on ? s.span : null); emit('hover', on ? s : null) }" @activate="links.flash(s.span); emit('activate', s)" />
          </div>
          <p v-if="s.source === 'heard' && marginNote(turns, s.span)" class="margin-note" :lang="fr">{{ marginNote(turns, s.span) }}</p>
        </div>
      </div>
      <slot :name="`step-${sec.step}`" />
    </fieldset>
    <slot name="after" />
  </section>
</template>

<style scoped>
.notice { padding: 20px 32px 8px; display: grid; gap: 18px; }
.nhead { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.nhead h2 { font-size: 22px; font-weight: 680; }
.ref { color: var(--cv-muted); font-size: 13.5px; font-weight: 600; }
.steps { padding: 2px 0 4px; }
.steps :deep([data-state="completed"] [data-slot="indicator"]), .steps :deep(.ended [data-slot="indicator"]) { background: var(--cv-fast); color: #fff; }
.sec { border: 0; margin: 0; padding: 0; min-width: 0; }
.shead { display: flex; align-items: center; gap: 10px; padding: 0 0 8px; }
.no {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 15px;
  background: var(--cv-ink); color: var(--cv-bg);
}
.st-current .no { background: var(--cv-orchid); color: var(--cv-on-orchid); }
.st-waiting .no, .st-open .no { background: var(--cv-sunk-2); color: var(--cv-ink); }
.shead h3 { font-size: 17px; font-weight: 650; }
.shead :deep(.cv-tag) { margin-left: auto; }
.boxes {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); background: var(--cv-surface);
  border-top: 1px solid var(--cv-rule); border-left: 1px solid var(--cv-rule); border-radius: 6px; overflow: hidden;
}
.box {
  border-right: 1px solid var(--cv-rule); border-bottom: 1px solid var(--cv-rule); padding: 9px 12px 11px;
  display: flex; flex-direction: column; gap: 5px; min-width: 0; transition: background-color 160ms;
}
.w2 { grid-column: span 2; } .w4 { grid-column: 1 / -1; }
.box.linked { background: var(--cv-orchid-wash); }
.box.empty { background: repeating-linear-gradient(-45deg, transparent 0 9px, color-mix(in srgb, var(--cv-sunk) 70%, transparent) 9px 10px); }
.k { font-size: 12px; font-weight: 650; color: var(--cv-muted); }
.v { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-height: 32px; }
.margin-note { margin: 0; }
.st-current .boxes { box-shadow: 0 0 0 2px var(--cv-orchid-wash); }
@media (max-width: 1180px) { .boxes { grid-template-columns: repeat(2, minmax(0, 1fr)); } .w4 { grid-column: 1 / -1; } }
@media (max-width: 720px) {
  .notice { padding: 16px 16px 8px; }
  .boxes { grid-template-columns: minmax(0, 1fr); }
  .w2, .w4 { grid-column: auto; }
}
</style>
