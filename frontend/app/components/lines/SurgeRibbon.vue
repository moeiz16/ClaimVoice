<script setup lang="ts">
// The surge ribbon: amber wash, what's happening in words, and the supervisor's two levers.
import type { Surge } from '~/types/api'
import { api } from '~/utils/api'

const props = defineProps<{ surge: Surge, queueWords?: string | null }>()
const emit = defineEmits<{ updated: [s: Surge] }>()
const { can } = useSession()
const listening = useListening()
const busy = ref(false)
const covered = ref(false)
const kindIcon = computed(() => (props.surge.kind === 'hail' ? 'hail' : props.surge.kind === 'flood' || props.surge.kind === 'rainfall' ? 'drop' : 'wind'))
const waitWords = computed(() => {
  const s = props.surge.waitForPersonSeconds
  return s < 60 ? 'under a minute' : s < 90 ? 'about 1 min' : `about ${Math.round(s / 60)} min`
})
const questionsWord = computed(() => `${props.surge.kindLabel} questions switched ${props.surge.surgeQuestionsOn ? 'on' : 'off'}`)

async function standby() {
  busy.value = true
  try {
    emit('updated', await api.switchboard.standby(props.surge.id))
    listening.flash('The standby team is on its way to the lines.')
  }
  catch { listening.flash('We couldn\'t reach the standby team. Try again.') }
  busy.value = false
}
async function toggleQuestions() {
  try { emit('updated', await api.switchboard.surgeQuestions(props.surge.id, !props.surge.surgeQuestionsOn)) }
  catch { listening.flash('That didn\'t change. Try again.') }
}
</script>

<template>
  <div class="surge" role="status">
    <span class="ic"><CvIcon :name="kindIcon" size="l" /></span>
    <div class="txt">
      <b>{{ surge.title }}</b><span class="headline"> · {{ surge.headline }}</span>
      <div class="facts">
        <span v-if="queueWords">{{ queueWords }}</span>
        <span v-else>Calls are <strong class="num">{{ surge.multiplier.toFixed(1) }}×</strong> usual {{ surge.sinceLabel }}</span>
        <button v-if="can('lines:manage')" type="button" class="fact-btn" :aria-pressed="surge.surgeQuestionsOn" @click="toggleQuestions">
          <CvIcon :name="surge.surgeQuestionsOn ? 'check' : 'plus'" size="s" />{{ questionsWord }}
        </button>
        <span v-else><CvIcon :name="surge.surgeQuestionsOn ? 'check' : 'x'" size="s" />{{ questionsWord }}</span>
        <span><CvIcon name="clock" size="s" />Wait for a person: {{ waitWords }}</span>
      </div>
    </div>
    <div class="act">
      <button v-if="can('lines:manage') && !surge.standbyCalled" class="btn primary sm" type="button" :disabled="busy" @click="standby">
        <CvIcon name="person" size="s" />Bring in the standby team ({{ surge.standbyAvailable }})
      </button>
      <span v-else-if="surge.standbyCalled" class="tag fast"><CvIcon name="check" size="s" />Standby team on the lines</span>
      <button class="btn soft sm on-sunk" type="button" :aria-expanded="covered" @click="covered = !covered">
        What's covered
      </button>
    </div>
    <p v-if="covered" class="guidance">
      <CvIcon name="shield" size="s" />{{ surge.guidance }} <span class="src">{{ surge.source }}</span>
    </p>
  </div>
</template>

<style scoped>
.surge { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; padding: 8px 10px 8px 12px; border-radius: 28px; background: var(--cv-siu-wash); }
.ic { width: 42px; height: 42px; border-radius: 50%; background: var(--cv-surface); display: grid; place-items: center; color: var(--cv-siu); flex: none; }
.txt { min-width: 0; }
b { font-family: var(--font-display); font-size: 19px; font-weight: 700; letter-spacing: -0.02em; }
.headline { color: var(--cv-muted); font-size: 14px; font-weight: 550; }
@media (max-width: 1280px) { .headline { display: none; } }
.facts { display: flex; gap: 18px; color: var(--cv-ink); font-size: 14px; font-weight: 550; flex-wrap: wrap; }
.facts > span, .fact-btn { display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }
.fact-btn { border: 0; background: none; padding: 0; font: inherit; color: inherit; border-radius: 8px; }
.fact-btn:hover { text-decoration: underline; text-underline-offset: 3px; }
strong { color: var(--cv-siu); font-weight: 800; }
.act { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.guidance { flex-basis: 100%; margin: 0 0 4px 58px; font-size: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.guidance .src { color: var(--cv-muted); font-size: 12.5px; }
@media (max-width: 720px) {
  .surge { padding: 12px; gap: 10px; }
  .facts { gap: 4px 12px; font-size: 13px; }
  .act { margin: 0; width: 100%; flex-wrap: wrap; }
  .act .btn { flex: 1 1 100%; }
  .guidance { margin-left: 0; }
}
</style>
