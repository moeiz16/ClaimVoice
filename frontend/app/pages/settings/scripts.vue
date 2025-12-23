<script setup lang="ts">
// Scripts per loss type, shown as the conversation: ClaimVoice's questions in order, in its own voice style, English
// and French side by side, each with ▸ Hear it, required or optional, and the fact it fills.
import type { Script, ScriptQuestion } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayShort } from '~/utils/format'
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
  <div class="scripts">
    <StateNote v-if="error" kind="error" title="That didn't load or save." :body="error" />
    <div class="types" role="tablist" aria-label="Loss type">
      <button v-for="s in scripts" :key="s.lossType" type="button" role="tab" class="pill" :aria-selected="active === s.lossType" @click="active = s.lossType">
        <CvIcon :name="lossIcon(s.lossType)" size="s" />{{ s.lossTypeLabel }}
      </button>
    </div>
    <section v-if="current" class="card convo" :aria-label="`${current.lossTypeLabel} script`">
      <header class="head">
        <h2>{{ current.lossTypeLabel }} questions</h2>
        <span class="muted">Version {{ current.version }}<template v-if="current.updatedBy"> · changed by {{ current.updatedBy.name }}, {{ fmtDayShort(current.updatedAt) }}</template></span>
      </header>
      <p v-if="draft.some(q => q.surgeOnly)" class="surge">
        <CvIcon name="wind" size="s" />Questions marked “storm” are asked only while a surge's questions are switched on from the line desk.
      </p>
      <ol class="qs">
        <li v-for="(q, i) in draft" :key="q.slotKey" class="q">
          <span class="n num">{{ i + 1 }}</span>
          <div class="pair">
            <div class="say">
              <span class="who"><i />ClaimVoice · English</span>
              <textarea v-if="manage" v-model="q.prompt.en" :rows="Math.max(1, Math.ceil(q.prompt.en.length / 64))" :aria-label="`Question ${i + 1} in English`" />
              <p v-else>
                {{ q.prompt.en }}
              </p>
              <button type="button" class="hear" @click="hear(q.prompt.en, 'en')">
                <CvIcon name="play" size="s" />Hear it
              </button>
            </div>
            <div class="say" lang="fr">
              <span class="who"><i />ClaimVoice · Français</span>
              <textarea v-if="manage" v-model="q.prompt.fr" :rows="Math.max(1, Math.ceil(q.prompt.fr.length / 64))" :aria-label="`Question ${i + 1} in French`" />
              <p v-else>
                {{ q.prompt.fr }}
              </p>
              <button type="button" class="hear" @click="hear(q.prompt.fr, 'fr')">
                <CvIcon name="play" size="s" />Écouter
              </button>
            </div>
          </div>
          <div class="meta">
            <span class="fills">Fills <b>{{ q.label }}</b></span>
            <button v-if="manage" type="button" class="tag" :class="q.required ? 'orchid' : 'plain'" :aria-pressed="q.required" @click="q.required = !q.required">
              <CvIcon :name="q.required ? 'check' : 'dots'" size="s" />{{ q.required ? 'Required' : 'Optional' }}
            </button>
            <CvTag v-else :kind="q.required ? 'orchid' : 'plain'" :icon="q.required ? 'check' : 'dots'">{{ q.required ? 'Required' : 'Optional' }}</CvTag>
            <CvTag v-if="q.surgeOnly" kind="siu" icon="wind">Storm</CvTag>
            <span v-if="q.when" class="muted">Only if {{ q.when.replace(/_/g, ' ').replace('== true', '') }}</span>
          </div>
        </li>
      </ol>
      <div v-if="manage" class="save">
        <input v-model="note" class="field-input sm" placeholder="What changed, for the activity log" aria-label="What changed">
        <button class="btn primary sm" type="button" :disabled="!dirty || busy" @click="save">
          Save as a new version
        </button>
        <span v-if="saved" class="tag fast"><CvIcon name="check" size="s" />{{ saved }}</span>
      </div>
    </section>
    <div v-else-if="!error" class="skeleton" style="height: 420px; border-radius: 28px" />
  </div>
</template>

<style scoped>
.scripts { display: grid; gap: 14px; }
.types { display: flex; gap: 6px; flex-wrap: wrap; }
.pill { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 14px; border-radius: 999px; border: 0; background: var(--cv-surface); font-weight: 650; font-size: 14px; color: var(--cv-muted); }
.pill[aria-selected="true"] { background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); box-shadow: inset 0 0 0 2px var(--cv-orchid); }
.convo { padding: 20px 22px; display: grid; gap: 12px; }
.head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.head h2 { font-size: 24px; font-weight: 700; letter-spacing: -0.025em; }
.muted { color: var(--cv-muted); font-size: 13.5px; }
.surge { margin: 0; display: flex; gap: 6px; align-items: center; font-size: 14px; background: var(--cv-siu-wash); border-radius: 14px; padding: 8px 12px; }
.qs { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.q { display: grid; grid-template-columns: 30px 1fr; gap: 6px 10px; padding: 12px; border-radius: 20px; background: var(--cv-sunk); }
.n { width: 26px; height: 26px; border-radius: 50%; background: var(--cv-surface); display: grid; place-items: center; font-size: 12px; font-weight: 800; color: var(--cv-muted); }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.say { background: var(--cv-surface); border-radius: 14px; padding: 8px 12px 6px; display: grid; gap: 4px; }
.who { display: flex; gap: 6px; align-items: center; font-size: 12px; font-weight: 750; color: var(--cv-muted); }
.who i { width: 7px; height: 7px; border-radius: 50%; background: var(--cv-orchid); }
.say p, .say textarea { margin: 0; font-family: var(--font-display); font-size: 16.5px; font-weight: 600; line-height: 1.3; letter-spacing: -0.012em; color: var(--cv-ink); }
.say textarea { border: 0; background: transparent; resize: vertical; padding: 2px 0; width: 100%; border-radius: 8px; }
.say textarea:focus { outline: 2px solid var(--cv-orchid-wash); }
.hear { justify-self: start; border: 0; background: none; color: var(--cv-orchid-ink); font-weight: 650; font-size: 13px; display: inline-flex; gap: 4px; align-items: center; padding: 2px 0; }
.meta { grid-column: 2; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.meta .tag { border: 0; }
.fills { font-size: 13px; color: var(--cv-muted); }
.save { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.save .field-input { max-width: 420px; }
@media (max-width: 900px) { .pair { grid-template-columns: 1fr; } }
</style>
