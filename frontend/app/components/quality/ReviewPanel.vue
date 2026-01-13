<script setup lang="ts">
// One call's quality review (DESIGN.md §5.5), the player first and the form on the same screen. The slate (caller,
// claim, time; the score), then the tape opened at the flagged moment ("Jumped to 4:10, where …") with the rubric
// pinned where each item was judged, the words around that moment, and the rubric as a form: numbered items, each
// with its verdict, its evidence, Agree / Disagree and a line on why; then a coaching note and Done → next call.
import type { CallDetail, QaScore, Recording, Transcript } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, fmtDayShort, fmtTime } from '~/utils/format'
import { beadIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'
import { ApiError } from '~/utils/http'
import type { ExtraPin } from '~/types/ui'

const props = defineProps<{ callId: string }>()
const emit = defineEmits<{ done: [] }>()
const { can } = useSession()
const score = ref<QaScore | null>(null)
const call = ref<CallDetail | null>(null)
const recording = ref<Recording | null>(null)
const transcript = ref<Transcript | null>(null)
const error = ref<string | null>(null)
const verdicts = ref<Record<string, string>>({})
const notes = ref<Record<string, string>>({})
const coaching = ref('')
const saving = ref(false)
const saved = ref(false)
const t = ref(0)
const rec = ref<{ seek: (s: number, play?: boolean) => void } | null>(null)

async function load() {
  error.value = null
  try {
    const [s, c] = await Promise.all([api.qa.score(props.callId), api.calls.get(props.callId)])
    score.value = s
    call.value = c
    for (const it of s.items) {
      if (it.reviewerVerdict) verdicts.value[it.key] = it.reviewerVerdict
      else if (s.status !== 'reviewed') verdicts.value[it.key] = 'agree'
      if (it.reviewerNote) notes.value[it.key] = it.reviewerNote
    }
    coaching.value = s.reviewNote ?? ''
    const [r, tr] = await Promise.all([
      can('recordings:read') ? api.calls.recording(props.callId).catch(() => (s.claimId ?? c.claimId) ? api.claims.recording((s.claimId ?? c.claimId)!).catch(() => null) : null) : Promise.resolve(null),
      api.calls.transcript(props.callId).catch(() => null),
    ])
    recording.value = r
    transcript.value = tr
    t.value = s.focus?.atSeconds ?? 0
  }
  catch (e) { error.value = (e as Error).message }
}
onMounted(load)

const items = computed(() => (score.value?.items ?? []).filter(i => i.passed !== null))
const pins = computed<ExtraPin[]>(() => items.value.filter(i => i.atSeconds != null).map(i => ({ atSeconds: i.atSeconds!, label: i.label, kind: i.passed === false ? 'fail' : 'pass' })))
const around = computed(() => {
  const turns = transcript.value?.turns ?? []
  const ms = (score.value?.focus?.atSeconds ?? t.value) * 1000
  const i = Math.max(0, turns.findIndex(x => x.endMs >= ms))
  return turns.slice(Math.max(0, i - 2), i + 4)
})
const ms = computed(() => t.value * 1000)
const caption = computed(() => {
  const s = score.value
  const c = call.value
  if (!s || !c) return null
  return `${s.claimNumber ?? c.reference} · ${fmtDayShort(c.startedAt)}, ${fmtTime(c.startedAt)} · ${c.lossTypeLabel ?? c.outcomeLabel}`
})
const BAND = { good: { kind: 'fast', icon: 'check' }, needs_attention: { kind: 'siu', icon: 'clock' }, failed: { kind: 'urgent', icon: 'urgent' } } as const
const VERDICTS = [{ value: 'agree', label: 'Agree' }, { value: 'disagree', label: 'Disagree' }]

async function submit() {
  if (!score.value) return
  saving.value = true
  try {
    score.value = await api.qa.review(props.callId, {
      items: items.value.map(i => ({ key: i.key, verdict: verdicts.value[i.key] === 'disagree' ? 'disagree' as const : 'agree' as const, note: notes.value[i.key] || null })),
      coachingNote: coaching.value.trim() || null,
    })
    saved.value = true
  }
  catch (e) { error.value = e instanceof ApiError ? e.message : 'That review didn\'t save. Try again.' }
  saving.value = false
}
</script>

<template>
  <div class="review">
    <Slate :title="call?.callerLabel ?? 'Quality review'" :caption="caption" :back="{ to: '/quality', label: 'Quality' }">
      <CvTag v-if="score" :kind="BAND[score.band].kind" :icon="BAND[score.band].icon" lg>
        {{ score.bandLabel }} · {{ Math.round(score.score) }} of 100
      </CvTag>
      <CvTag v-if="score?.reviewedBy && !saved" kind="plain" icon="check" class="hide-phone">
        Reviewed by {{ score.reviewedBy.name }}
      </CvTag>
    </Slate>

    <StateNote v-if="error" kind="error" title="We couldn't open this review." :body="error" retry class="m-4 sm:mx-8" @retry="load" />

    <template v-if="score && call">
      <p v-if="score.focus" class="focus">
        <UIcon name="i-lucide-flag" class="size-5 flex-none" />
        <span class="ft">{{ score.focus.text }}</span>
        <UButton v-if="recording?.available" size="sm" color="neutral" variant="soft" icon="i-lucide-play" @click="rec?.seek(score.focus.atSeconds, true)">
          Play from {{ fmtClock(score.focus.atSeconds) }}
        </UButton>
      </p>

      <CallRecording
        v-if="recording" ref="rec" :recording="recording" :caller-label="firstName(call.callerLabel)" :start-at="score.focus?.atSeconds ?? null"
        :extra-pins="pins" :turns="transcript?.turns ?? null" label="The call's recording" @time="x => (t = x)"
      />

      <section class="sec beadsec" aria-labelledby="beads-h">
        <h2 id="beads-h" class="sr-only-cv">
          The rubric at a glance
        </h2>
        <RubricBeads :beads="score.beads" />
      </section>

      <section v-if="around.length" class="sec" aria-labelledby="around-h">
        <h2 id="around-h">
          Around this moment
        </h2>
        <ol class="around">
          <li v-for="x in around" :key="x.id" class="t" :class="[x.speaker, { on: ms >= x.atMs && ms < x.endMs + 400 }]">
            <button type="button" class="tm num" :aria-label="`Play from ${fmtClock(x.atMs / 1000)}`" :disabled="!recording?.available" @click="rec?.seek(x.atMs / 1000, true)">
              {{ fmtClock(x.atMs / 1000) }}
            </button>
            <div>
              <b>{{ x.speaker === 'caller' ? firstName(x.speakerLabel) : x.speakerLabel }}</b>
              <p :lang="x.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="x.text" :turn-id="x.id" />
              </p>
              <span v-if="x.textEn" class="en">{{ x.textEn }}</span>
            </div>
          </li>
        </ol>
      </section>

      <section class="sec" aria-labelledby="rubric-h">
        <h2 id="rubric-h">
          Each item, and whether you agree
        </h2>
        <ol class="items">
          <li v-for="(i, n) in items" :key="i.key" class="item" :class="i.passed ? 'ok' : 'miss'">
            <span class="no num" aria-hidden="true">{{ n + 1 }}</span>
            <div class="body">
              <div class="ih">
                <h3><UIcon :name="icon(beadIcon(i.key))" class="size-4" />{{ i.label }}</h3>
                <CvTag :kind="i.passed ? 'fast' : 'urgent'" :icon="i.passed ? 'check' : 'x'">
                  {{ i.passed ? 'Met' : 'Missed' }}
                </CvTag>
                <button v-if="i.atSeconds != null" class="heard chip" type="button" :aria-label="`Play from ${fmtClock(i.atSeconds)}`" @click="rec?.seek(i.atSeconds!, true)">
                  <span class="at"><UIcon name="i-lucide-play" class="tri" />{{ fmtClock(i.atSeconds) }}</span>
                </button>
              </div>
              <p class="note">
                {{ i.note }}
              </p>
              <blockquote v-for="(ev, k) in i.evidence" :key="k" class="quote">
                “{{ ev.quote }}”
              </blockquote>
            </div>
            <div v-if="can('qa:review')" class="verdict">
              <URadioGroup
                v-model="verdicts[i.key]" :items="VERDICTS" orientation="horizontal" variant="card" size="sm" color="primary"
                :legend="`Do you agree: ${i.label}`" :ui="{ legend: 'sr-only-cv', item: 'py-1.5 px-3 rounded-md' }"
              />
              <UInput v-if="verdicts[i.key] === 'disagree'" v-model="notes[i.key]" size="md" class="w-full" :aria-label="`Why you disagree: ${i.label}`" placeholder="Why you disagree, in a line" />
            </div>
            <p v-else-if="i.reviewerVerdict" class="verdict muted">
              Reviewer {{ i.reviewerVerdict === 'agree' ? 'agreed' : 'disagreed' }}<template v-if="i.reviewerNote">: {{ i.reviewerNote }}</template>
            </p>
          </li>
        </ol>
      </section>

      <section v-if="can('qa:review')" class="sec coach" aria-label="Coaching and done">
        <UFormField label="Coaching note to the script owner" hint="Optional" class="w-full">
          <UTextarea v-model="coaching" :maxlength="600" :rows="3" autoresize class="w-full" placeholder="Acknowledge an injury before asking about the damage." />
        </UFormField>
        <div class="acts">
          <UButton :loading="saving" trailing-icon="i-lucide-chevron-right" @click="saved ? emit('done') : submit()">
            {{ saved ? 'Next call' : 'Done' }}
          </UButton>
          <CvTag v-if="saved" kind="fast" icon="check">
            Review saved and logged
          </CvTag>
        </div>
      </section>
    </template>

    <div v-else-if="!error" aria-busy="true" aria-label="Loading the review">
      <Tape label="Loading the recording">
        <template #key>
          <USkeleton class="size-14 rounded-full" />
        </template>
        <USkeleton class="h-full w-full" />
      </Tape>
      <div class="sec">
        <div class="flex flex-wrap gap-1.5">
          <USkeleton v-for="b in 6" :key="b" class="h-7 w-28 rounded-full" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.focus {
  margin: 0; display: flex; align-items: center; gap: 10px 12px; flex-wrap: wrap; padding: 14px 32px 0; background: var(--cv-sunk);
  color: var(--cv-orchid-ink); font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 19px; font-weight: 620; letter-spacing: -0.01em;
}
.focus .ft { flex: 1 1 320px; min-width: 0; }
.sec { padding: 18px 32px 20px; border-bottom: 1px solid var(--cv-rule); }
.sec h2 { font-size: 19px; font-weight: 660; margin-bottom: 10px; }
.beadsec { padding-top: 14px; padding-bottom: 14px; }
.around { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--cv-rule); }
.t { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 8px; padding: 8px 12px; border-bottom: 1px solid var(--cv-rule); border-left: 3px solid transparent; font-size: 15px; line-height: 1.5; }
.t.on { background: var(--cv-orchid-wash); border-left-color: var(--cv-orchid); }
.t b { display: block; font-size: 12px; color: var(--cv-muted); line-height: 1.3; }
.t p { margin: 0; }
.t.caller p { color: var(--cv-caller); }
.en { display: block; color: var(--cv-muted); font-size: 13.5px; }
.tm { border: 0; background: none; color: var(--cv-muted); font-size: 12px; font-weight: 650; padding: 3px 0 0; text-align: left; align-self: start; cursor: pointer; }
.tm:hover:not(:disabled) { color: var(--cv-orchid-ink); }
.items { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--cv-rule); }
.item { display: grid; grid-template-columns: 28px minmax(0, 1fr) minmax(220px, 300px); gap: 8px 16px; align-items: start; padding: 14px 0; border-bottom: 1px solid var(--cv-rule); }
.no {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 14px;
}
.ok .no { background: var(--cv-fast-wash); color: var(--cv-fast); }
.miss .no { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.body { min-width: 0; display: grid; gap: 6px; }
.ih { display: flex; align-items: center; gap: 8px 10px; flex-wrap: wrap; }
.ih h3 { font-family: var(--font-sans); font-variation-settings: normal; font-size: 16px; font-weight: 650; display: inline-flex; gap: 6px; align-items: center; letter-spacing: 0; }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.note { margin: 0; color: var(--cv-muted); font-size: 14.5px; }
.quote { margin: 0; padding-left: 12px; border-left: 2px solid var(--cv-caller-wash); font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 16px; font-weight: 540; color: var(--cv-caller); }
.verdict { display: grid; gap: 8px; justify-items: stretch; }
.verdict.muted { margin: 0; color: var(--cv-muted); font-size: 14px; }
.coach { display: grid; gap: 12px; }
.acts { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
@media (max-width: 1100px) {
  .item { grid-template-columns: 28px minmax(0, 1fr); }
  .verdict { grid-column: 2; }
}
@media (max-width: 720px) {
  .focus { padding: 12px 16px 0; font-size: 16.5px; }
  .sec { padding: 14px 16px 16px; }
}
</style>
