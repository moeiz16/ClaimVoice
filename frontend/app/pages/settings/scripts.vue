<script setup lang="ts">
// Scripts per loss type, read as the conversation: ClaimVoice's questions in order, in its own voice, English and
// French side by side, each with ▸ Hear it, required or optional, and the fact it fills. Saving makes a new version.
import type { Script, ScriptQuestion } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayShort } from '~/utils/format'
import { icon } from '~/utils/icons'
import { lossIcon } from '~/utils/labels'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const scripts = ref<Script[]>([])
const active = ref<string>('')
const draft = ref<ScriptQuestion[]>([])
const note = ref('')
const error = ref<string | null>(null)
const saved = ref<string | null>(null)
const busy = ref(false)

onMounted(async () => {
  try {
    scripts.value = await api.settings.scripts()
    active.value = scripts.value.find(s => s.lossType === 'wind')?.lossType ?? scripts.value[0]?.lossType ?? ''
  }
  catch (e) { error.value = (e as Error).message }
})
const types = computed(() => scripts.value.map(s => ({ value: s.lossType, label: s.lossTypeLabel, icon: icon(lossIcon(s.lossType)) })))
const current = computed(() => scripts.value.find(s => s.lossType === active.value) ?? null)
watch(current, (s) => { draft.value = s ? s.questions.map(q => ({ ...q, prompt: { ...q.prompt } })) : []; saved.value = null })
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(current.value?.questions ?? []))

function hear(text: string, lang: 'en' | 'fr') {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang === 'fr' ? 'fr-CA' : 'en-CA'
  window.speechSynthesis.speak(u)
}

async function save() {
  if (!current.value) return
  busy.value = true
  error.value = null
  try {
    const s = await api.settings.saveScript(current.value.lossType, draft.value, note.value.trim() || 'Wording updated')
    scripts.value = scripts.value.map(x => (x.lossType === s.lossType ? s : x))
    saved.value = `Saved as version ${s.version}. New calls use it from now on.`
    note.value = ''
  }
  catch (e) { error.value = (e as Error).message }
  busy.value = false
}
</script>

<template>
  <div>
    <StateNote v-if="error" kind="error" class="m-4 sm:mx-8" title="That didn't load or save." :body="error" />
    <div v-if="types.length" class="picker">
      <UTabs v-model="active" :items="types" :content="false" variant="pill" size="sm" color="neutral" aria-label="Loss type" />
    </div>

    <section v-if="current" class="convo" :aria-label="`${current.lossTypeLabel} script`">
      <header class="head">
        <h2>{{ current.lossTypeLabel }} questions</h2>
        <span class="muted">Version {{ current.version }}<template v-if="current.updatedBy"> · changed by {{ current.updatedBy.name }}, {{ fmtDayShort(current.updatedAt) }}</template></span>
      </header>
      <p v-if="draft.some(q => q.surgeOnly)" class="surge">
        <UIcon name="i-lucide-wind" class="size-4 shrink-0" />Questions marked “storm” are asked only while a surge's questions are switched on from the line desk.
      </p>

      <div class="cols" aria-hidden="true">
        <span /><span class="who"><i />ClaimVoice · English</span><span class="who"><i />ClaimVoice · Français</span><span class="who">What it fills</span>
      </div>
      <ol class="qs">
        <li v-for="(q, i) in draft" :key="q.slotKey" class="q">
          <span class="n num">{{ i + 1 }}</span>
          <div class="say">
            <span class="who narrow"><i />ClaimVoice · English</span>
            <UTextarea v-if="manage" v-model="q.prompt.en" variant="ghost" autoresize :rows="1" class="w-full" :ui="{ base: 'say-text px-0' }" :aria-label="`Question ${i + 1} in English`" />
            <p v-else class="say-text">
              {{ q.prompt.en }}
            </p>
            <UButton variant="link" size="sm" icon="i-lucide-play" class="px-0 self-start" @click="hear(q.prompt.en, 'en')">
              Hear it
            </UButton>
          </div>
          <div class="say" lang="fr">
            <span class="who narrow"><i />ClaimVoice · Français</span>
            <UTextarea v-if="manage" v-model="q.prompt.fr" variant="ghost" autoresize :rows="1" class="w-full" :ui="{ base: 'say-text px-0' }" :aria-label="`Question ${i + 1} in French`" />
            <p v-else class="say-text">
              {{ q.prompt.fr }}
            </p>
            <UButton variant="link" size="sm" icon="i-lucide-play" class="px-0 self-start" @click="hear(q.prompt.fr, 'fr')">
              Écouter
            </UButton>
          </div>
          <div class="meta">
            <span class="fills">Fills <b>{{ q.label }}</b></span>
            <template v-if="manage">
              <USwitch v-model="q.required" size="sm" :label="q.required ? 'Required' : 'Optional'" :aria-label="`Question ${i + 1} is required`" />
              <USwitch v-model="q.surgeOnly" size="sm" color="warning" label="Storm only" :aria-label="`Question ${i + 1} is asked only in a storm`" />
            </template>
            <span v-else class="flex gap-1.5 flex-wrap">
              <CvTag :kind="q.required ? 'orchid' : 'plain'" :icon="q.required ? 'check' : 'dots'">{{ q.required ? 'Required' : 'Optional' }}</CvTag>
              <CvTag v-if="q.surgeOnly" kind="siu" icon="wind">Storm</CvTag>
            </span>
            <span v-if="q.when" class="muted">Only if {{ q.when.replace(/_/g, ' ').replace('== true', '') }}</span>
          </div>
        </li>
      </ol>

      <div v-if="manage" class="save">
        <UFormField label="What changed, for the activity log" name="note" class="w-full max-w-[460px]">
          <UInput v-model="note" placeholder="Wording updated" class="w-full" />
        </UFormField>
        <UButton :loading="busy" :disabled="!dirty || busy" icon="i-lucide-check" @click="save">
          Save as a new version
        </UButton>
        <CvTag v-if="saved" kind="fast" icon="check" role="status">
          {{ saved }}
        </CvTag>
      </div>
    </section>
    <div v-else-if="!error" class="convo" aria-busy="true" aria-label="Loading the scripts">
      <USkeleton v-for="n in 5" :key="n" class="h-16 w-full" />
    </div>
  </div>
</template>

<style scoped>
.picker { padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); overflow-x: auto; }
.convo { padding: 20px 32px 28px; display: grid; gap: 12px; }
.head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.head h2 { font-size: 24px; font-weight: 700; }
.muted { color: var(--cv-muted); font-size: 13.5px; }
.surge { margin: 0; display: flex; gap: 6px; align-items: center; font-size: 14px; color: var(--cv-siu); }
.cols, .q { display: grid; grid-template-columns: 36px minmax(0, 1fr) minmax(0, 1fr) 220px; gap: 6px 24px; }
.cols { padding-bottom: 6px; border-bottom: 1px solid var(--cv-rule); margin-top: 6px; }
.qs { list-style: none; margin: 0; padding: 0; }
.q { padding: 14px 0; border-bottom: 1px solid var(--cv-rule); align-items: start; }
.n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 20px; font-weight: 720; color: var(--cv-orchid-ink); line-height: 1.3; }
.say { display: grid; gap: 2px; min-width: 0; }
.who { display: flex; gap: 6px; align-items: center; font-size: 12.5px; font-weight: 650; color: var(--cv-muted); }
.who i { width: 7px; height: 7px; border-radius: 50%; background: var(--cv-orchid); }
.who.narrow { display: none; }
.say-text, .say :deep(.say-text) { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 17px; font-weight: 560; line-height: 1.35; color: var(--cv-ink); }
.meta { display: grid; gap: 8px; align-content: start; justify-items: start; }
.fills { font-size: 13.5px; color: var(--cv-muted); }
.fills b { color: var(--cv-ink); }
.save { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; padding-top: 8px; }
@media (max-width: 1100px) {
  .cols { display: none; }
  .q { grid-template-columns: 30px minmax(0, 1fr) minmax(0, 1fr); }
  .meta { grid-column: 2 / -1; grid-auto-flow: column; justify-content: start; align-items: center; }
  .who.narrow { display: flex; }
}
@media (max-width: 720px) {
  .picker { padding: 12px 16px; }
  .convo { padding: 16px 16px 24px; }
  .q { grid-template-columns: 26px minmax(0, 1fr); gap: 8px 10px; }
  .q > .say, .meta { grid-column: 2; }
  .meta { grid-auto-flow: row; }
}
</style>
