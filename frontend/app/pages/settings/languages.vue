<script setup lang="ts">
// Languages: English and French (Canada), the voice and speed for each, French first for Québec numbers.
import type { Languages } from '~/types/api'
import { api } from '~/utils/api'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const langs = ref<Languages | null>(null)
const msg = ref<string | null>(null)
onMounted(async () => { langs.value = await api.settings.languages() })
const names: Record<string, string> = { en: 'English', fr: 'Français (Canada)' }
const sample: Record<string, string> = { en: 'Larkspur Mutual claims, this is ClaimVoice. Is everyone safe right now?', fr: 'Réclamations Larkspur Mutual, ici ClaimVoice. Est-ce que tout le monde est en sécurité?' }

function hear(lang: string) {
  if (!('speechSynthesis' in window) || !langs.value) return
  const u = new SpeechSynthesisUtterance(sample[lang])
  u.lang = lang === 'fr' ? 'fr-CA' : 'en-CA'
  u.rate = langs.value.voices[lang]?.speed ?? 1
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(u)
}
async function save() {
  if (!langs.value) return
  try { langs.value = await api.settings.saveLanguages(langs.value); msg.value = 'Saved.' }
  catch (e) { msg.value = (e as Error).message }
}
</script>

<template>
  <div v-if="langs" class="grid">
    <section v-for="l in (['en', 'fr'] as const)" :key="l" class="card lang" :lang="l === 'fr' ? 'fr' : undefined">
      <header>
        <h2>{{ names[l] }}</h2>
        <CvTag :kind="langs.enabled.includes(l) ? 'fast' : 'plain'" :icon="langs.enabled.includes(l) ? 'check' : 'x'">{{ langs.enabled.includes(l) ? 'Answering in this language' : 'Off' }}</CvTag>
        <CvTag v-if="langs.default === l" kind="orchid" icon="lang">First language</CvTag>
      </header>
      <p class="say">
        “{{ sample[l] }}”
      </p>
      <div v-if="langs.voices[l]" class="row">
        <span class="k">Voice</span><span class="v">{{ langs.voices[l]!.voice }}</span>
        <button type="button" class="btn soft sm" @click="hear(l)">
          <CvIcon name="play" size="s" />Hear it
        </button>
      </div>
      <div v-if="langs.voices[l]" class="row">
        <label class="k" :for="`speed-${l}`">Speed</label>
        <input :id="`speed-${l}`" v-model.number="langs.voices[l]!.speed" type="range" min="0.8" max="1.2" step="0.05" :disabled="!manage">
        <span class="v num">{{ langs.voices[l]!.speed.toFixed(2) }}×</span>
      </div>
    </section>
    <section class="card lang wide">
      <h2>How the line picks a language</h2>
      <label class="check"><input v-model="langs.detectAutomatically" type="checkbox" :disabled="!manage">Switch to the caller's language as soon as they speak it</label>
      <p class="muted">
        <CvIcon name="pin" size="s" />French first for Québec numbers ({{ langs.frenchFirstRegions.join(', ').replace('CA-QC', 'Québec') }}), as Québec's Charter of the French language expects. Every greeting offers both.
      </p>
      <div v-if="manage" class="save">
        <button class="btn primary sm" type="button" @click="save">
          Save
        </button>
        <span v-if="msg" class="tag fast"><CvIcon name="check" size="s" />{{ msg }}</span>
      </div>
    </section>
  </div>
  <div v-else class="skeleton" style="height: 300px; border-radius: 28px" />
</template>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.lang { padding: 18px 20px; display: grid; gap: 10px; align-content: start; }
.wide { grid-column: 1 / -1; }
header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-right: 4px; }
.say { margin: 0; font-family: var(--font-display); font-size: 18px; font-weight: 600; letter-spacing: -0.015em; background: var(--cv-sunk); border-radius: 14px; padding: 10px 12px; }
.row { display: grid; grid-template-columns: 70px 1fr auto; gap: 10px; align-items: center; }
.k { color: var(--cv-muted); font-size: 13px; font-weight: 650; }
.v { font-weight: 650; }
input[type="range"] { accent-color: var(--cv-orchid); }
.check { display: flex; gap: 10px; align-items: center; font-weight: 600; }
.check input { accent-color: var(--cv-orchid); width: 18px; height: 18px; }
.muted { margin: 0; color: var(--cv-muted); font-size: 14px; display: flex; gap: 6px; align-items: center; }
.save { display: flex; gap: 10px; align-items: center; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
