<script setup lang="ts">
// Privacy: the person accountable for personal information (PIPEDA, Québec's Law 25) and the notice callers can read.
import type { Privacy } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const p = ref<Privacy | null>(null)
const msg = ref<{ ok: boolean, text: string } | null>(null)
onMounted(async () => { p.value = await api.settings.privacy() })
async function save() {
  if (!p.value) return
  try { p.value = await api.settings.savePrivacy(p.value); msg.value = { ok: true, text: 'Saved.' } }
  catch (e) { msg.value = { ok: false, text: e instanceof ApiError ? e.message : 'That didn\'t save.' } }
}
</script>

<template>
  <div v-if="p" class="grid">
    <form class="card body" @submit.prevent="save">
      <h2>Privacy officer</h2>
      <p class="muted">
        The person callers and regulators can reach about personal information. Named in the recording notice and on the photo-upload page.
      </p>
      <label for="po-name">Name</label>
      <input id="po-name" v-model="p.privacyOfficerName" class="field-input sm" :disabled="!manage" autocomplete="off">
      <label for="po-email">Email</label>
      <input id="po-email" v-model="p.privacyOfficerEmail" class="field-input sm" type="email" :disabled="!manage" autocomplete="off">
      <label for="po-url">Privacy notice link</label>
      <input id="po-url" v-model="p.privacyNoticeUrl" class="field-input sm" type="url" :disabled="!manage" placeholder="https://" autocomplete="off">
      <div v-if="manage" class="save">
        <button class="btn primary sm" type="submit">
          Save
        </button>
        <span v-if="msg" class="tag" :class="msg.ok ? 'fast' : 'urgent'"><CvIcon :name="msg.ok ? 'check' : 'urgent'" size="s" />{{ msg.text }}</span>
      </div>
    </form>
    <section class="card tint body">
      <h2>What ClaimVoice keeps, in short</h2>
      <ul>
        <li><CvIcon name="shield" size="s" />Recordings only after consent; where everyone must agree, nothing before the yes.</li>
        <li><CvIcon name="card" size="s" />Card numbers are cut before anything is stored, and never shown.</li>
        <li><CvIcon name="lock" size="s" />Phone numbers, emails and postal codes are masked on every screen.</li>
        <li><CvIcon name="camera" size="s" />Photo location details are removed on upload.</li>
        <li><CvIcon name="lang" size="s" />French calls are kept in French, with English shown for staff.</li>
        <li><CvIcon name="phone" size="s" />Demo calls from the website are never kept.</li>
      </ul>
    </section>
  </div>
  <div v-else class="skeleton" style="height: 320px; border-radius: 28px" />
</template>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: start; }
.body { padding: 18px 22px 22px; display: grid; gap: 8px; }
h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
.muted { margin: 0 0 6px; color: var(--cv-muted); font-size: 14px; }
label { font-size: 13px; font-weight: 700; color: var(--cv-muted); margin-top: 6px; }
.save { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
li { display: flex; gap: 8px; align-items: flex-start; font-size: 15px; }
li :deep(svg) { color: var(--cv-orchid-ink); margin-top: 3px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
