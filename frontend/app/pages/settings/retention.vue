<script setup lang="ts">
// Retention, as sentences with editable blanks, one per ruled line. Card-number moments are always removed;
// refused-consent transcripts are never kept. Both are locked statements.
import type { Retention } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDateShort, fmtDayShort, fmtTime } from '~/utils/format'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const r = ref<Retention | null>(null)
const msg = ref<{ ok: boolean, text: string } | null>(null)
const busy = ref(false)
onMounted(async () => { r.value = await api.settings.retention() })
const years = [1, 2, 3, 5, 7, 10].map(y => ({ value: y, label: `${y} year${y > 1 ? 's' : ''}` }))
const blank = { base: 'font-sans font-semibold text-[15px] text-orchid-ink bg-orchid-wash', trailingIcon: 'text-orchid-ink' }
async function save() {
  if (!r.value) return
  busy.value = true
  try { r.value = await api.settings.saveRetention(r.value); msg.value = { ok: true, text: 'Saved. The nightly clean-up follows it from tonight.' } }
  catch (e) { msg.value = { ok: false, text: (e as Error).message } }
  busy.value = false
}
</script>

<template>
  <section v-if="r" class="doc" aria-label="Retention">
    <p class="rule">
      <UIcon name="i-lucide-volume-2" class="size-5 ic" />Keep recordings for
      <USelect v-model="r.recordingsYears" :items="years" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Years to keep recordings" />.
    </p>
    <p class="rule">
      <UIcon name="i-lucide-file-text" class="size-5 ic" />Keep transcripts for
      <USelect v-model="r.transcriptsYears" :items="years" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Years to keep transcripts" />.
    </p>
    <p class="rule">
      <UIcon name="i-lucide-camera" class="size-5 ic" />Keep photos for
      <USelect v-model="r.photosYears" :items="years" :disabled="!manage" variant="none" class="blank" :ui="blank" aria-label="Years to keep photos" />.
    </p>
    <p class="rule">
      <UIcon name="i-lucide-file-text" class="size-5 ic" />Claim files are kept for <b>{{ r.claimFilesYears }} years</b>, as claims records.
      <span class="lk"><UIcon name="i-lucide-lock" class="size-4" />Set by policy</span>
    </p>
    <p class="rule">
      <UIcon name="i-lucide-credit-card" class="size-5 ic" />Remove card-number moments: <b>always</b>. <span class="hush">■■■■ removed</span>
      <span class="lk"><UIcon name="i-lucide-lock" class="size-4" />Can't be turned off</span>
    </p>
    <p class="rule">
      <UIcon name="i-lucide-shield-check" class="size-5 ic" />When a caller says no to recording, their words are <b>not kept</b>; notes only.
      <span class="lk"><UIcon name="i-lucide-lock" class="size-4" />Can't be turned off</span>
    </p>
    <div class="queue">
      <CvTag :kind="r.deletionRequestsWaiting ? 'siu' : 'fast'" :icon="r.deletionRequestsWaiting ? 'clock' : 'check'">
        {{ r.deletionRequestsWaiting ? `${r.deletionRequestsWaiting} deletion request${r.deletionRequestsWaiting > 1 ? 's' : ''} waiting` : 'No deletion requests waiting' }}
      </CvTag>
      <span v-if="r.lastPurgeAt" class="muted">Last clean-up {{ fmtDayShort(r.lastPurgeAt) }}, {{ fmtTime(r.lastPurgeAt) }}</span>
      <span v-if="r.nextPurgeOn" class="muted">· next {{ fmtDateShort(r.nextPurgeOn) }}</span>
    </div>
    <div v-if="manage" class="save">
      <UButton icon="i-lucide-check" :loading="busy" @click="save">
        Save
      </UButton>
      <CvTag v-if="msg" :kind="msg.ok ? 'fast' : 'urgent'" :icon="msg.ok ? 'check' : 'urgent'" role="status">
        {{ msg.text }}
      </CvTag>
    </div>
  </section>
  <div v-else class="doc" aria-busy="true" aria-label="Loading retention">
    <div v-for="n in 6" :key="n" class="rule">
      <USkeleton class="h-8 w-2/3" />
    </div>
  </div>
</template>

<style scoped>
.doc { display: grid; }
.rule { margin: 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 16px 32px; border-bottom: 1px solid var(--cv-rule); font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 20px; font-weight: 520; }
.rule .ic { color: var(--cv-orchid-ink); }
.rule b { font-weight: 720; }
.blank { display: inline-flex; width: auto; }
.lk { margin-left: auto; display: inline-flex; gap: 6px; align-items: center; font-family: var(--font-sans); font-variation-settings: normal; font-size: 13px; font-weight: 650; color: var(--cv-muted); }
.queue { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 16px 32px 0; }
.muted { color: var(--cv-muted); font-size: 13.5px; }
.save { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 16px 32px 28px; }
@media (max-width: 720px) {
  .rule { font-size: 17px; padding: 14px 16px; }
  .lk { margin-left: 0; }
  .queue { padding: 14px 16px 0; }
  .save { padding: 14px 16px 22px; }
}
</style>
