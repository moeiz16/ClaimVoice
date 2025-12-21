<script setup lang="ts">
// Retention, as sentences with editable blanks. Card-number moments are always removed; refused-consent transcripts
// are never kept. Both are locked.
import type { Retention } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDateShort, fmtDayShort, fmtTime } from '~/utils/format'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const r = ref<Retention | null>(null)
const msg = ref<string | null>(null)
onMounted(async () => { r.value = await api.settings.retention() })
const years = [1, 2, 3, 5, 7, 10]
async function save() {
  if (!r.value) return
  try { r.value = await api.settings.saveRetention(r.value); msg.value = 'Saved. The nightly clean-up follows it from tonight.' }
  catch (e) { msg.value = (e as Error).message }
}
</script>

<template>
  <section v-if="r" class="card body">
    <p class="rule">
      <CvIcon name="volume" />Keep recordings for
      <select v-model.number="r.recordingsYears" class="inline-blank" :disabled="!manage" aria-label="Years to keep recordings">
        <option v-for="y in years" :key="y" :value="y">{{ y }} year{{ y > 1 ? 's' : '' }}</option>
      </select>.
    </p>
    <p class="rule">
      <CvIcon name="doc" />Keep transcripts for
      <select v-model.number="r.transcriptsYears" class="inline-blank" :disabled="!manage" aria-label="Years to keep transcripts">
        <option v-for="y in years" :key="y" :value="y">{{ y }} year{{ y > 1 ? 's' : '' }}</option>
      </select>.
    </p>
    <p class="rule">
      <CvIcon name="camera" />Keep photos for
      <select v-model.number="r.photosYears" class="inline-blank" :disabled="!manage" aria-label="Years to keep photos">
        <option v-for="y in years" :key="y" :value="y">{{ y }} year{{ y > 1 ? 's' : '' }}</option>
      </select>.
    </p>
    <p class="rule locked">
      <CvIcon name="doc" />Claim files are kept for <b>{{ r.claimFilesYears }} years</b>, as claims records.
      <span class="lk"><CvIcon name="lock" size="s" />Set by policy</span>
    </p>
    <p class="rule locked">
      <CvIcon name="card" />Remove card-number moments: <b>always</b>. <span class="hush">■■■■ removed</span>
      <span class="lk"><CvIcon name="lock" size="s" />Can't be turned off</span>
    </p>
    <p class="rule locked">
      <CvIcon name="shield" />When a caller says no to recording, their words are <b>not kept</b>; notes only.
      <span class="lk"><CvIcon name="lock" size="s" />Can't be turned off</span>
    </p>
    <div class="queue">
      <CvTag :kind="r.deletionRequestsWaiting ? 'siu' : 'fast'" :icon="r.deletionRequestsWaiting ? 'clock' : 'check'">
        {{ r.deletionRequestsWaiting ? `${r.deletionRequestsWaiting} deletion request${r.deletionRequestsWaiting > 1 ? 's' : ''} waiting` : 'No deletion requests waiting' }}
      </CvTag>
      <span v-if="r.lastPurgeAt" class="muted">Last clean-up {{ fmtDayShort(r.lastPurgeAt) }}, {{ fmtTime(r.lastPurgeAt) }}</span>
      <span v-if="r.nextPurgeOn" class="muted">· next {{ fmtDateShort(r.nextPurgeOn) }}</span>
    </div>
    <div v-if="manage" class="save">
      <button class="btn primary sm" type="button" @click="save">
        Save
      </button>
      <span v-if="msg" class="tag fast"><CvIcon name="check" size="s" />{{ msg }}</span>
    </div>
  </section>
  <div v-else class="skeleton" style="height: 380px; border-radius: 28px" />
</template>

<style scoped>
.body { padding: 14px 22px 20px; display: grid; gap: 4px; }
.rule { margin: 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 12px 0; border-bottom: 1px solid var(--cv-sunk); font-family: var(--font-display); font-size: 20px; font-weight: 550; letter-spacing: -0.015em; }
.rule > :deep(svg) { color: var(--cv-orchid-ink); }
.rule b { font-weight: 750; }
.locked { color: var(--cv-ink); }
.lk { margin-left: auto; display: inline-flex; gap: 6px; align-items: center; font-family: var(--font-sans); font-size: 13px; font-weight: 650; color: var(--cv-muted); letter-spacing: 0; }
.inline-blank { font-family: var(--font-sans); font-size: 15px; appearance: none; padding-right: 14px; }
.queue { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding-top: 14px; }
.muted { color: var(--cv-muted); font-size: 13.5px; }
.save { display: flex; gap: 10px; align-items: center; padding-top: 14px; }
@media (max-width: 720px) { .rule { font-size: 17px; } .lk { margin-left: 0; } }
</style>
