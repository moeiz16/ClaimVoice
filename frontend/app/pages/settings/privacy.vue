<script setup lang="ts">
// Privacy: the person accountable for personal information (PIPEDA, Québec's Law 25) and the notice callers can
// read, then what ClaimVoice keeps, in short.
import type { Privacy } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const p = ref<Privacy | null>(null)
const msg = ref<{ ok: boolean, text: string } | null>(null)
const busy = ref(false)
onMounted(async () => { p.value = await api.settings.privacy() })
async function save() {
  if (!p.value) return
  busy.value = true
  try { p.value = await api.settings.savePrivacy(p.value); msg.value = { ok: true, text: 'Saved.' } }
  catch (e) { msg.value = { ok: false, text: e instanceof ApiError ? e.message : 'That didn\'t save.' } }
  busy.value = false
}
const noticeUrl = computed({
  get: () => p.value?.privacyNoticeUrl ?? '',
  set: (v: string) => { if (p.value) p.value.privacyNoticeUrl = v || null },
})
</script>

<template>
  <div v-if="p" class="doc">
    <section class="sec" aria-labelledby="po-h">
      <div class="lead">
        <h2 id="po-h">
          Privacy officer
        </h2>
        <p class="muted">
          The person callers and regulators can reach about personal information. Named in the recording notice and on the photo-upload page.
        </p>
      </div>
      <form class="form" @submit.prevent="save">
        <UFormField label="Name" name="name">
          <UInput v-model="p.privacyOfficerName" :disabled="!manage" autocomplete="off" class="w-full" />
        </UFormField>
        <UFormField label="Email" name="email">
          <UInput v-model="p.privacyOfficerEmail" type="email" :disabled="!manage" autocomplete="off" icon="i-lucide-mail" class="w-full" />
        </UFormField>
        <UFormField label="Privacy notice link" name="url">
          <UInput v-model="noticeUrl" type="url" :disabled="!manage" placeholder="https://" autocomplete="off" icon="i-lucide-link" class="w-full" />
        </UFormField>
        <div v-if="manage" class="save">
          <UButton type="submit" icon="i-lucide-check" :loading="busy">
            Save
          </UButton>
          <CvTag v-if="msg" :kind="msg.ok ? 'fast' : 'urgent'" :icon="msg.ok ? 'check' : 'urgent'" role="status">
            {{ msg.text }}
          </CvTag>
        </div>
      </form>
    </section>

    <section class="sec" aria-labelledby="keep-h">
      <div class="lead">
        <h2 id="keep-h">
          What ClaimVoice keeps, in short
        </h2>
      </div>
      <ul class="keeps">
        <li><UIcon name="i-lucide-shield-check" class="size-4 shrink-0" />Recordings only after consent; where everyone must agree, nothing before the yes.</li>
        <li><UIcon name="i-lucide-credit-card" class="size-4 shrink-0" />Card numbers are cut before anything is stored, and never shown.</li>
        <li><UIcon name="i-lucide-lock" class="size-4 shrink-0" />Phone numbers, emails and postal codes are masked on every screen.</li>
        <li><UIcon name="i-lucide-camera" class="size-4 shrink-0" />Photo location details are removed on upload.</li>
        <li><UIcon name="i-lucide-languages" class="size-4 shrink-0" />French calls are kept in French, with English shown for staff.</li>
        <li><UIcon name="i-lucide-phone" class="size-4 shrink-0" />Demo calls from the website are never kept.</li>
      </ul>
    </section>
  </div>
  <div v-else class="doc" aria-busy="true" aria-label="Loading privacy">
    <div v-for="n in 2" :key="n" class="sec">
      <USkeleton class="h-8 w-48" /><USkeleton class="h-40 w-full" />
    </div>
  </div>
</template>

<style scoped>
.doc { display: grid; gap: 3px; border-radius: 28px; overflow: hidden; }
.sec { display: grid; grid-template-columns: minmax(200px, 320px) minmax(0, 1fr); gap: 12px 32px; align-items: start; padding: 20px 24px; background: var(--cv-surface); }
.lead { display: grid; gap: 6px; }
h2 { font-size: 22px; font-weight: 900; }
.muted { margin: 0; color: var(--cv-muted); font-size: 14px; }
.form { display: grid; gap: 14px; max-width: 520px; }
.save { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.keeps { list-style: none; margin: 0; padding: 0; max-width: 720px; }
.keeps li { display: flex; gap: 10px; align-items: flex-start; font-size: 15px; padding: 10px 0; border-bottom: 2px solid var(--cv-sunk); }
.keeps li:last-child { border-bottom: 0; }
.keeps li :deep(svg), .keeps li > span:first-child { color: var(--cv-jade-ink); margin-top: 3px; }
@media (max-width: 900px) { .sec { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 720px) { .sec { padding: 16px; } }
</style>
