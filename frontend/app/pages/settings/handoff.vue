<script setup lang="ts">
// Hand-off rules written as sentences with editable blanks.
import type { HandoffRules } from '~/types/api'
import { api } from '~/utils/api'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const rules = ref<HandoffRules | null>(null)
const saved = ref<HandoffRules | null>(null)
const word = ref('')
const msg = ref<string | null>(null)
onMounted(async () => { rules.value = await api.settings.handoffRules(); saved.value = structuredClone(toRaw(rules.value)) })
const dirty = computed(() => JSON.stringify(rules.value) !== JSON.stringify(saved.value))
const times = [{ v: 1, l: 'once' }, { v: 2, l: 'twice' }, { v: 3, l: 'three times' }]

function addWord() {
  const w = word.value.trim().toLowerCase()
  if (w && rules.value && !rules.value.urgentKeywords.includes(w)) rules.value.urgentKeywords.push(w)
  word.value = ''
}
async function save() {
  if (!rules.value) return
  try {
    rules.value = await api.settings.saveHandoffRules(rules.value)
    saved.value = structuredClone(toRaw(rules.value))
    msg.value = 'Saved. New calls follow these rules.'
  }
  catch (e) { msg.value = (e as Error).message }
}
</script>

<template>
  <section v-if="rules" class="card body">
    <div class="rule">
      <span class="ic urgent"><CvIcon name="urgent" /></span>
      <p>
        If the caller mentions
        <span class="chips">
          <span v-for="(k, i) in rules.urgentKeywords" :key="k" class="chip">{{ k }}<button v-if="manage" type="button" :aria-label="`Remove ${k}`" @click="rules.urgentKeywords.splice(i, 1)"><CvIcon name="x" size="s" /></button></span>
          <input v-if="manage" v-model="word" class="add" placeholder="add a word" aria-label="Add an urgent word" @keydown.enter.prevent="addWord">
        </span>,
        <b>bring in a person now.</b>
        <span class="lock"><CvIcon name="lock" size="s" />Urgent safety always reaches a person; this can't be turned off.</span>
      </p>
    </div>
    <div class="rule">
      <span class="ic"><CvIcon name="person" /></span>
      <p>
        If the caller asks for a person
        <select v-model.number="rules.askedTimes" class="inline-blank" :disabled="!manage" aria-label="How many times">
          <option v-for="t in times" :key="t.v" :value="t.v">{{ t.l }}</option>
        </select>,
        <b>bring in a person.</b>
      </p>
    </div>
    <div class="rule">
      <span class="ic"><CvIcon name="whisper" /></span>
      <p>
        If ClaimVoice isn't sure what it heard
        <select v-model.number="rules.lowConfidenceTurns" class="inline-blank" :disabled="!manage" aria-label="Turns in a row">
          <option v-for="n in [1, 2, 3, 4, 5]" :key="n" :value="n">{{ n === 1 ? 'once' : n === 2 ? 'twice in a row' : `${n} times in a row` }}</option>
        </select>,
        <b>offer a person.</b>
      </p>
    </div>
    <div class="rule">
      <span class="ic"><CvIcon name="shield" /></span>
      <p>
        If the caller can't confirm who they are after
        <select v-model.number="rules.identityAttempts" class="inline-blank" :disabled="!manage" aria-label="Attempts">
          <option v-for="n in [1, 2, 3, 4, 5]" :key="n" :value="n">{{ n }} {{ n === 1 ? 'try' : 'tries' }}</option>
        </select>,
        <b>bring in a person.</b> ClaimVoice never guesses a policy for someone else.
      </p>
    </div>
    <div class="rule">
      <span class="ic"><CvIcon name="clock" /></span>
      <p>
        If nobody picks up within
        <select v-model.number="rules.maxWaitSeconds" class="inline-blank" :disabled="!manage" aria-label="Wait">
          <option v-for="s in [60, 90, 120, 180]" :key="s" :value="s">{{ s < 120 ? `${s} seconds` : `${s / 60} minutes` }}</option>
        </select>,
        <b>offer a call-back</b> and let ClaimVoice finish the claim file. Urgent calls never go back to the line.
      </p>
    </div>
    <div class="rule">
      <span class="ic"><CvIcon name="x" /></span>
      <p>
        If the caller doesn't want to be recorded,
        <button v-if="manage" type="button" class="inline-blank" :aria-pressed="rules.offerPersonOnConsentRefusal" @click="rules.offerPersonOnConsentRefusal = !rules.offerPersonOnConsentRefusal">
          {{ rules.offerPersonOnConsentRefusal ? 'offer a person' : 'carry on taking notes' }}
        </button>
        <b v-else>{{ rules.offerPersonOnConsentRefusal ? 'offer a person' : 'carry on taking notes' }}</b>.
      </p>
    </div>
    <div v-if="manage" class="save">
      <button class="btn primary sm" type="button" :disabled="!dirty" @click="save">
        Save the rules
      </button>
      <span v-if="msg" class="tag fast"><CvIcon name="check" size="s" />{{ msg }}</span>
    </div>
  </section>
  <div v-else class="skeleton" style="height: 380px; border-radius: 28px" />
</template>

<style scoped>
.body { padding: 10px 22px 20px; display: grid; }
.rule { display: grid; grid-template-columns: 44px 1fr; gap: 12px; align-items: start; padding: 16px 0; border-bottom: 1px solid var(--cv-sunk); }
.ic { width: 40px; height: 40px; border-radius: 50%; background: var(--cv-sunk); display: grid; place-items: center; color: var(--cv-orchid-ink); }
.ic.urgent { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.rule p { margin: 0; font-family: var(--font-display); font-size: 20px; font-weight: 550; line-height: 1.6; letter-spacing: -0.015em; }
.rule b { font-weight: 750; }
.chips { display: inline-flex; flex-wrap: wrap; gap: 6px; vertical-align: middle; }
.chip { display: inline-flex; align-items: center; gap: 4px; height: 34px; padding: 0 6px 0 12px; border-radius: 999px; background: var(--cv-urgent-wash); color: var(--cv-urgent); font-family: var(--font-sans); font-size: 14px; font-weight: 700; }
.chip button { border: 0; background: none; color: inherit; display: grid; place-items: center; padding: 2px; border-radius: 50%; }
.add { height: 34px; border-radius: 999px; border: 1.5px dashed var(--cv-faint); background: transparent; padding: 0 12px; font: inherit; font-size: 14px; width: 120px; color: var(--cv-ink); }
.inline-blank { font-family: var(--font-sans); font-size: 15px; vertical-align: middle; }
select.inline-blank { appearance: none; padding-right: 14px; }
.lock { display: flex; gap: 6px; align-items: center; font-family: var(--font-sans); font-size: 13px; color: var(--cv-muted); font-weight: 600; letter-spacing: 0; }
.save { display: flex; gap: 10px; align-items: center; padding-top: 16px; }
@media (max-width: 720px) { .rule p { font-size: 17px; } }
</style>
