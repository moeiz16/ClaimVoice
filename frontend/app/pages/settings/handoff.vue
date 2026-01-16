<script setup lang="ts">
// Hand-off rules, written as sentences with editable blanks, one rule per ruled line.
import type { HandoffRules } from '~/types/api'
import { api } from '~/utils/api'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const rules = ref<HandoffRules | null>(null)
const saved = ref<HandoffRules | null>(null)
const msg = ref<{ ok: boolean, text: string } | null>(null)
const busy = ref(false)
onMounted(async () => { rules.value = await api.settings.handoffRules(); saved.value = structuredClone(toRaw(rules.value)) })
const dirty = computed(() => JSON.stringify(rules.value) !== JSON.stringify(saved.value))

const times = [{ value: 1, label: 'once' }, { value: 2, label: 'twice' }, { value: 3, label: 'three times' }]
const unsure = [1, 2, 3, 4, 5].map(n => ({ value: n, label: n === 1 ? 'once' : n === 2 ? 'twice in a row' : `${n} times in a row` }))
const tries = [1, 2, 3, 4, 5].map(n => ({ value: n, label: `${n} ${n === 1 ? 'try' : 'tries'}` }))
const waits = [60, 90, 120, 180].map(s => ({ value: s, label: s < 120 ? `${s} seconds` : `${s / 60} minutes` }))
const refusal = [{ value: 'person', label: 'offer a person' }, { value: 'notes', label: 'carry on taking notes' }]
const onRefusal = computed({
  get: () => (rules.value?.offerPersonOnConsentRefusal ? 'person' : 'notes'),
  set: (v: string) => { if (rules.value) rules.value.offerPersonOnConsentRefusal = v === 'person' },
})

// Urgent words are kept lower-case and once each.
function setWords(words: string[]) {
  if (!rules.value) return
  rules.value.urgentKeywords = [...new Set(words.map(w => w.trim().toLowerCase()).filter(Boolean))]
}
const blank = { base: 'font-sans font-semibold text-[15px] text-jade-ink bg-jade-wash', trailingIcon: 'text-jade-ink' }

async function save() {
  if (!rules.value) return
  busy.value = true
  try {
    rules.value = await api.settings.saveHandoffRules(rules.value)
    saved.value = structuredClone(toRaw(rules.value))
    msg.value = { ok: true, text: 'Saved. New calls follow these rules.' }
  }
  catch (e) { msg.value = { ok: false, text: (e as Error).message } }
  busy.value = false
}
</script>

<template>
  <section v-if="rules" class="doc" aria-label="Hand-off rules">
    <div class="rule">
      <span class="ic urgent"><UIcon name="i-lucide-triangle-alert" class="size-5" /></span>
      <div>
        <p>
          If the caller mentions
          <UInputTags
            v-if="manage" :model-value="rules.urgentKeywords" placeholder="add a word" color="error" variant="soft" size="lg"
            class="words" aria-label="Urgent words" :ui="{ root: 'font-sans', item: 'bg-urgent-wash text-urgent font-bold ring-0 rounded-full px-2.5', itemDelete: 'text-urgent', input: 'w-28' }" @update:model-value="setWords"
          />
          <span v-else class="inline-flex flex-wrap gap-1.5 align-middle">
            <CvTag v-for="k in rules.urgentKeywords" :key="k" kind="urgent" icon="urgent">{{ k }}</CvTag>
          </span>,
          <b>bring in a person now.</b>
        </p>
        <p class="lock">
          <UIcon name="i-lucide-lock" class="size-4" />Urgent safety always reaches a person; this can't be turned off.
        </p>
      </div>
    </div>
    <div class="rule">
      <span class="ic"><UIcon name="i-lucide-user-round" class="size-5" /></span>
      <p>
        If the caller asks for a person
        <USelectMenu v-model="rules.askedTimes" :items="times" value-key="value" :search-input="false" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="How many times" />,
        <b>bring in a person.</b>
      </p>
    </div>
    <div class="rule">
      <span class="ic"><UIcon name="i-lucide-message-square-more" class="size-5" /></span>
      <p>
        If ClaimVoice isn't sure what it heard
        <USelectMenu v-model="rules.lowConfidenceTurns" :items="unsure" value-key="value" :search-input="false" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Turns in a row" />,
        <b>offer a person.</b>
      </p>
    </div>
    <div class="rule">
      <span class="ic"><UIcon name="i-lucide-shield-check" class="size-5" /></span>
      <p>
        If the caller can't confirm who they are after
        <USelectMenu v-model="rules.identityAttempts" :items="tries" value-key="value" :search-input="false" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Attempts" />,
        <b>bring in a person.</b> ClaimVoice never guesses a policy for someone else.
      </p>
    </div>
    <div class="rule">
      <span class="ic"><UIcon name="i-lucide-clock" class="size-5" /></span>
      <p>
        If nobody picks up within
        <USelectMenu v-model="rules.maxWaitSeconds" :items="waits" value-key="value" :search-input="false" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Wait" />,
        <b>offer a call-back</b> and let ClaimVoice finish the claim file. Urgent calls never go back to the line.
      </p>
    </div>
    <div class="rule">
      <span class="ic"><UIcon name="i-lucide-x" class="size-5" /></span>
      <p>
        If the caller doesn't want to be recorded,
        <USelectMenu v-if="manage" v-model="onRefusal" :items="refusal" value-key="value" :search-input="false" variant="none" class="blank" :ui="blank" aria-label="When the caller says no to recording" />
        <b v-else>{{ rules.offerPersonOnConsentRefusal ? 'offer a person' : 'carry on taking notes' }}</b>.
      </p>
    </div>
    <div v-if="manage" class="save">
      <UButton icon="i-lucide-check" :loading="busy" :disabled="!dirty || busy" @click="save">
        Save the rules
      </UButton>
      <CvTag v-if="msg" :kind="msg.ok ? 'fast' : 'urgent'" :icon="msg.ok ? 'check' : 'urgent'" role="status">
        {{ msg.text }}
      </CvTag>
    </div>
  </section>
  <div v-else class="doc" aria-busy="true" aria-label="Loading the hand-off rules">
    <div v-for="n in 6" :key="n" class="rule">
      <USkeleton class="size-10 rounded-full" /><USkeleton class="h-8 w-3/4" />
    </div>
  </div>
</template>

<style scoped>
.doc { display: grid; gap: 3px; border-radius: 28px; overflow: hidden; }
.rule { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 16px; align-items: start; padding: 20px 24px; background: var(--cv-surface); }
.ic { width: 40px; height: 40px; border-radius: 50%; background: var(--cv-sunk); display: grid; place-items: center; color: var(--cv-jade-ink); }
.ic.urgent { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.rule p { margin: 0; font-family: var(--font-round); font-size: 20px; font-weight: 520; line-height: 1.7; max-width: 980px; }
.rule b { font-weight: 800; }
.blank { display: inline-flex; vertical-align: middle; width: auto; min-width: 0; }
.words { display: inline-flex; vertical-align: middle; max-width: 100%; }
.rule p.lock { display: flex; gap: 6px; align-items: center; font-family: var(--font-sans); font-size: 13px; line-height: 1.4; color: var(--cv-muted); font-weight: 600; margin-top: 6px; }
.save { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 18px 0 8px; }
@media (max-width: 720px) {
  .rule { padding: 14px 16px; grid-template-columns: 36px minmax(0, 1fr); gap: 12px; }
  .ic { width: 34px; height: 34px; }
  .rule p { font-size: 17px; }
}
</style>
