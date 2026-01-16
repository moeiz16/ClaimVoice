<script setup lang="ts">
// The answer sheet (DESIGN.md §3): the claim file written as ClaimVoice's questions and the caller's answers. Each
// script step is a question bubble on the left (with its state in a word); the answers sit in one bubble on the
// right, each value with its source: a heard pebble with ▸ time (press it to hear or see the words), "from the
// policy", or a dashed "Not heard yet". The step being asked shows typing dots; steps not reached yet are dashed.
// Slots: `before` (e.g. In short), `step-N` (extra content in an answer, e.g. photos for 5), `after` (where it goes).
import type { Lang, Slot } from '~/types/api'
import { linkKey } from '~/composables/useHeardLinks'
import { boxWidth } from '~/utils/notice'
import type { NoticeSection } from '~/utils/notice'

const props = withDefaults(defineProps<{
  sections: NoticeSection[]
  step: number
  ended?: boolean
  language?: Lang
  /** Words for the sheet's own labels: staff screens stay in English; the caller's demo line can be French. */
  words?: Lang
  loading?: boolean
  title?: string
  reference?: string | null
}>(), { ended: false, language: 'en', words: 'en', loading: false, title: 'Claim file', reference: null })

const emit = defineEmits<{ activate: [slot: Slot], hover: [slot: Slot | null] }>()
const links = useHeardLinks()
const isLinked = (s: Slot) => !!s.span && (links.active.value === linkKey(s.span) || links.flashKey.value === linkKey(s.span))
const fr = computed(() => (props.language === 'fr' ? 'fr' : undefined))

/** The question ClaimVoice asks at each script step. */
const QUESTIONS: Record<number, [string, string]> = {
  1: ['May we record this call?', 'Pouvons-nous enregistrer cet appel ?'],
  2: ['Who\'s calling, and on which policy?', 'Qui appelle, et pour quel contrat ?'],
  3: ['Is everyone safe?', 'Tout le monde est-il en sécurité ?'],
  4: ['What happened?', 'Que s\'est-il passé ?'],
  5: ['Can you send photos?', 'Pouvez-vous envoyer des photos ?'],
  6: ['What does the policy cover?', 'Que couvre le contrat ?'],
  7: ['Did we get it all right?', 'Avons-nous tout bien noté ?'],
}
const question = (step: number) => (QUESTIONS[step] ?? QUESTIONS[7]!)[props.words === 'fr' ? 1 : 0]

const STATE = {
  done: { kind: 'fast', icon: 'check', word: 'Answered' },
  current: { kind: 'jade', icon: 'waves', word: 'Asking now' },
  open: { kind: 'siu', icon: 'clock', word: 'Still open' },
  waiting: { kind: 'plain', icon: 'clock', word: 'Not asked yet' },
} as const
const STATE_FR = { done: 'Répondu', current: 'En cours', open: 'Encore ouvert', waiting: 'Pas encore demandé' } as const
function stateWord(sec: NoticeSection): string {
  const verified = sec.key.startsWith('caller') && sec.state === 'done'
  if (props.words === 'fr') return verified ? 'Vérifié' : STATE_FR[sec.state]
  return verified ? 'Verified' : STATE[sec.state].word
}
// Pop: an answer that arrives while you watch pops in once. Answers already there when the sheet opens don't.
const seen = new Set<string>()
const ready = ref(false)
onMounted(() => { setTimeout(() => { ready.value = true }, 800) })
function fresh(s: Slot): boolean {
  if (!s.display || seen.has(s.key)) return false
  seen.add(s.key)
  return ready.value
}
</script>

<template>
  <section class="sheet" :aria-label="title">
    <header class="shead">
      <h2>{{ title }}</h2>
      <span v-if="reference" class="ref num">{{ reference }}</span>
      <slot name="head" />
    </header>
    <slot name="before" />
    <div v-if="loading" class="qa" aria-busy="true">
      <USkeleton v-for="n in 3" :key="n" class="h-28 rounded-[24px]" />
    </div>
    <ol v-else class="qa">
      <li v-for="sec in sections" :key="sec.key" class="pair" :class="`st-${sec.state}`" :data-step="sec.step">
        <div class="q">
          <CvMark :size="30" />
          <div class="qb">
            <h3 :lang="words === 'fr' ? 'fr' : undefined">
              {{ question(sec.step) }}
            </h3>
            <span class="qmeta">
              <span class="sec-t">{{ sec.title }}</span>
              <CvTag :kind="STATE[sec.state].kind" :icon="STATE[sec.state].icon">{{ stateWord(sec) }}</CvTag>
            </span>
          </div>
        </div>
        <div class="a">
          <dl class="vals">
            <div v-for="s in sec.slots" :key="s.key" class="kv" :class="[`w${boxWidth(s)}`, { linked: isLinked(s), empty: !s.display, popped: fresh(s) }]">
              <dt>{{ s.label }}</dt>
              <dd>
                <HeardValue :field="s" :linked="isLinked(s)" :lang="fr" @hover="on => { links.hover(on ? s.span : null); emit('hover', on ? s : null) }" @activate="links.flash(s.span); emit('activate', s)" />
              </dd>
            </div>
          </dl>
          <span v-if="sec.state === 'current'" class="typing" aria-hidden="true"><i /><i /><i /></span>
          <slot :name="`step-${sec.step}`" />
        </div>
      </li>
    </ol>
    <slot name="after" />
  </section>
</template>

<style scoped>
.sheet { display: grid; gap: 18px; }
.shead { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.shead h2 { font-size: 30px; font-weight: 900; letter-spacing: -0.02em; }
.ref { color: var(--cv-muted); font-size: 14px; font-weight: 500; }
.qa { list-style: none; margin: 0; padding: 0; display: grid; gap: 22px; }
.pair { display: grid; gap: 10px; }
.q { display: flex; align-items: flex-end; gap: 10px; max-width: min(640px, 92%); }
.qb { padding: 12px 18px 12px; border-radius: 22px 22px 22px 6px; background: var(--cv-jade-wash); display: grid; gap: 6px; }
.q h3 { font-size: 21px; line-height: 1.2; font-weight: 850; }
.qmeta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sec-t { font-size: 13px; color: var(--cv-jade-ink); font-weight: 500; }
.a {
  justify-self: end; width: min(860px, 94%); padding: 14px 16px 16px; border-radius: 22px 22px 6px 22px;
  background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); display: grid; gap: 10px;
}
.st-waiting .a { background: transparent; box-shadow: inset 0 0 0 2px var(--cv-rule); border: 0; }
.st-waiting .qb { background: var(--cv-sunk); }
.st-current .a { box-shadow: 0 0 0 3px var(--cv-seaglass), var(--cv-shadow-soft); }
.vals { margin: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.kv { padding: 8px 10px 10px; border-radius: 16px; background: var(--cv-bg); display: grid; gap: 4px; align-content: start; min-width: 0; transition: background-color 160ms; }
.w2 { grid-column: span 2; } .w4 { grid-column: 1 / -1; }
.kv.linked { background: var(--cv-jade-wash); }
.kv.empty { background: transparent; box-shadow: inset 0 0 0 2px var(--cv-sunk); }
.kv.popped { animation: pop var(--m-pop) var(--ease-tide); }
dt { font-size: 12.5px; font-weight: 500; color: var(--cv-muted); }
dd { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-height: 34px; }
.typing { color: var(--cv-jade); padding: 2px 6px; }
@media (max-width: 1180px) { .vals { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
  .shead h2 { font-size: 24px; }
  .q h3 { font-size: 18px; }
  .a { width: 100%; padding: 12px; }
  .vals { grid-template-columns: minmax(0, 1fr); }
  .w2, .w4 { grid-column: auto; }
}
</style>
