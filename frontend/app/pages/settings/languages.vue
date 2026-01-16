<script setup lang="ts">
// Languages: English and French (Canada), the voice and speed for each, French first for Québec numbers. One ruled
// line per language, then how the line picks between them.
import type { Languages } from '~/types/api'
import { api } from '~/utils/api'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const langs = ref<Languages | null>(null)
const msg = ref<{ ok: boolean, text: string } | null>(null)
const busy = ref(false)
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
  busy.value = true
  try { langs.value = await api.settings.saveLanguages(langs.value); msg.value = { ok: true, text: 'Saved.' } }
  catch (e) { msg.value = { ok: false, text: (e as Error).message } }
  busy.value = false
}
</script>

<template>
  <div v-if="langs" class="doc">
    <section v-for="l in (['en', 'fr'] as const)" :key="l" class="lang" :lang="l === 'fr' ? 'fr' : undefined" :aria-labelledby="`lang-${l}`">
      <div class="name">
        <h2 :id="`lang-${l}`">
          {{ names[l] }}
        </h2>
        <span class="flex flex-wrap gap-1.5">
          <CvTag :kind="langs.enabled.includes(l) ? 'fast' : 'plain'" :icon="langs.enabled.includes(l) ? 'check' : 'x'">{{ langs.enabled.includes(l) ? 'Answering in this language' : 'Off' }}</CvTag>
          <CvTag v-if="langs.default === l" kind="jade" icon="lang">First language</CvTag>
        </span>
      </div>
      <div class="said">
        <p class="say">
          {{ l === 'fr' ? `« ${sample[l]} »` : `“${sample[l]}”` }}
        </p>
        <UButton variant="link" size="sm" icon="i-lucide-play" class="px-0 self-start" @click="hear(l)">
          {{ l === 'fr' ? 'Écouter' : 'Hear it' }}
        </UButton>
      </div>
      <dl v-if="langs.voices[l]" class="voice-set">
        <dt>Voice</dt>
        <dd class="font-semibold">
          {{ langs.voices[l]!.voice }}
        </dd>
        <dt :id="`speed-${l}`">
          Speed
        </dt>
        <dd class="speed">
          <USlider v-model="langs.voices[l]!.speed" :min="0.8" :max="1.2" :step="0.05" :disabled="!manage" size="sm" class="w-40" :aria-labelledby="`speed-${l}`" />
          <span class="num font-semibold">{{ langs.voices[l]!.speed.toFixed(2) }}×</span>
        </dd>
      </dl>
    </section>

    <section class="lang pick" aria-labelledby="lang-pick">
      <h2 id="lang-pick">
        How the line picks a language
      </h2>
      <div class="grid gap-3">
        <USwitch v-model="langs.detectAutomatically" :disabled="!manage" label="Switch to the caller's language as soon as they speak it" :ui="{ label: 'text-[15px] font-semibold text-ink' }" />
        <p class="muted">
          <UIcon name="i-lucide-map-pin" class="size-4 shrink-0" />French first for Québec numbers ({{ langs.frenchFirstRegions.join(', ').replace('CA-QC', 'Québec') }}), as Québec's Charter of the French language expects. Every greeting offers both.
        </p>
      </div>
    </section>

    <div v-if="manage" class="save">
      <UButton icon="i-lucide-check" :loading="busy" @click="save">
        Save
      </UButton>
      <CvTag v-if="msg" :kind="msg.ok ? 'fast' : 'urgent'" :icon="msg.ok ? 'check' : 'urgent'" role="status">
        {{ msg.text }}
      </CvTag>
    </div>
  </div>
  <div v-else class="doc" aria-busy="true" aria-label="Loading the languages">
    <div v-for="n in 3" :key="n" class="lang">
      <USkeleton class="h-8 w-40" /><USkeleton class="h-14 w-full" /><USkeleton class="h-14 w-full" />
    </div>
  </div>
</template>

<style scoped>
.doc { display: grid; gap: 3px; border-radius: 28px; overflow: hidden; }
.lang { display: grid; grid-template-columns: minmax(200px, 260px) minmax(0, 1.4fr) minmax(220px, 1fr); gap: 12px 32px; align-items: start; padding: 20px 24px; background: var(--cv-surface); }
.pick { grid-template-columns: minmax(200px, 260px) minmax(0, 1fr); }
.name { display: grid; gap: 8px; justify-items: start; }
h2 { font-size: 22px; font-weight: 900; }
.said { display: grid; gap: 2px; }
.say { margin: 0; font-family: var(--font-round); font-size: 18px; font-weight: 560; line-height: 1.35; }
.voice-set { margin: 0; display: grid; grid-template-columns: 64px 1fr; gap: 10px 12px; align-items: center; }
.voice-set dt { color: var(--cv-muted); font-size: 13px; font-weight: 500; }
.voice-set dd { margin: 0; }
.speed { display: flex; gap: 12px; align-items: center; }
.muted { margin: 0; color: var(--cv-muted); font-size: 14px; display: flex; gap: 6px; align-items: flex-start; }
.muted :deep(svg), .muted > span:first-child { margin-top: 2px; }
.save { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 18px 0 8px; }
@media (max-width: 1100px) {
  .lang, .pick { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .lang { padding: 16px; }
}
</style>
