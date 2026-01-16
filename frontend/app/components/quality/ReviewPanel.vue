<script setup lang="ts">
// One call's quality review (DESIGN.md §3), the player first and the checklist on the same screen. The crumb and the
// caller, the score, then the flag ("Jumped to 4:10, where …") as a bubble, the recording opened at that moment with
// each rubric item pinned where it was judged, the conversation around that moment as bubbles, and the rubric as a
// checklist of round ticks: each item's verdict, its evidence, Agree / Disagree and a line on why; then a coaching
// note and Done → the next call.
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
const aroundIds = computed(() => around.value.filter(x => ms.value >= x.atMs && ms.value < x.endMs + 400).map(x => x.id))
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
    <PageHead :title="call?.callerLabel ?? 'Quality review'" :caption="caption" :back="{ to: '/quality', label: 'Quality' }">
      <CvTag v-if="score" :kind="BAND[score.band].kind" :icon="BAND[score.band].icon" lg>
        {{ score.bandLabel }} · {{ Math.round(score.score) }} of 100
      </CvTag>
      <CvTag v-if="score?.reviewedBy && !saved" kind="plain" icon="check" class="hide-phone">
        Reviewed by {{ score.reviewedBy.name }}
      </CvTag>
    </PageHead>

    <StateNote v-if="error" kind="error" title="We couldn't open this review." :body="error" retry class="mb-4" @retry="load" />

    <template v-if="score && call">
      <div v-if="score.focus" class="focus">
        <span class="fic" aria-hidden="true"><UIcon name="i-lucide-flag" /></span>
        <p class="ft round">
          {{ score.focus.text }}
        </p>
        <UButton v-if="recording?.available" color="neutral" icon="i-lucide-play" @click="rec?.seek(score.focus.atSeconds, true)">
          Play from {{ fmtClock(score.focus.atSeconds) }}
        </UButton>
      </div>

      <CallRecording
        v-if="recording" ref="rec" :recording="recording" :caller-label="firstName(call.callerLabel)" :start-at="score.focus?.atSeconds ?? null"
        :extra-pins="pins" label="The call's recording" @time="x => (t = x)"
      />

      <section v-if="around.length" class="sec" aria-labelledby="around-h">
        <h2 id="around-h" class="pool-h">
          Around this moment
        </h2>
        <Conversation
          :turns="around" :caller-label="call.callerLabel" :seekable="!!recording?.available" :current-id="aroundIds[0] ?? null"
          label="Around this moment" @seek="s => rec?.seek(s, true)"
        />
      </section>

      <section class="sec" aria-labelledby="rubric-h">
        <h2 id="rubric-h" class="pool-h">
          Each item, and whether you agree
        </h2>
        <RubricBeads :beads="score.beads" class="beadrow" />
        <ol class="items">
          <li v-for="i in items" :key="i.key" class="item" :class="i.passed ? 'ok' : 'miss'">
            <span class="tick" aria-hidden="true"><UIcon :name="i.passed ? 'i-lucide-check' : 'i-lucide-x'" /></span>
            <div class="body">
              <div class="ih">
                <h3><UIcon :name="icon(beadIcon(i.key))" class="size-5" />{{ i.label }}</h3>
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
                {{ ev.quote }}
              </blockquote>
            </div>
            <div v-if="can('qa:review')" class="verdict">
              <URadioGroup
                v-model="verdicts[i.key]" :items="VERDICTS" orientation="horizontal" variant="card" size="sm" color="primary"
                :legend="`Do you agree: ${i.label}`" :ui="{ legend: 'sr-only-cv', item: 'py-2 px-3.5 rounded-full' }"
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
          <UButton size="xl" :loading="saving" trailing-icon="i-lucide-chevron-right" @click="saved ? emit('done') : submit()">
            {{ saved ? 'Next call' : 'Done' }}
          </UButton>
          <CvTag v-if="saved" kind="fast" icon="check">
            Review saved and logged
          </CvTag>
        </div>
      </section>
    </template>

    <div v-else-if="!error" aria-busy="true" aria-label="Loading the review" class="grid gap-4">
      <USkeleton class="h-20 rounded-[28px]" />
      <USkeleton class="h-44 rounded-[32px]" />
    </div>
  </div>
</template>

<style scoped>
.focus { display: flex; align-items: center; gap: 12px 16px; flex-wrap: wrap; padding: 16px 20px; margin-bottom: 18px; border-radius: 6px 28px 28px 28px; background: var(--cv-urgent-wash); }
.fic { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-urgent); color: #fff; font-size: 20px; flex: none; }
[data-theme="dark"] .fic { color: var(--cv-bg); }
.ft { margin: 0; flex: 1 1 320px; min-width: 0; font-size: 21px; line-height: 1.25; font-weight: 850; color: var(--cv-ink); }
.sec { margin-top: 36px; display: grid; gap: 14px; }
.beadrow { margin-bottom: 4px; }
.items { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.item { display: grid; grid-template-columns: 56px minmax(0, 1fr) minmax(230px, 300px); gap: 10px 18px; align-items: start; padding: 18px 20px; border-radius: 26px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.tick { width: 52px; height: 52px; border-radius: 50%; display: grid; place-items: center; font-size: 26px; }
.ok .tick { background: var(--cv-fast-wash); color: var(--cv-fast); }
.miss .tick { background: var(--cv-urgent); color: #fff; }
[data-theme="dark"] .miss .tick { color: var(--cv-bg); }
.body { min-width: 0; display: grid; gap: 8px; }
.ih { display: flex; align-items: center; gap: 8px 10px; flex-wrap: wrap; }
.ih h3 { font-size: 20px; font-weight: 850; display: inline-flex; gap: 8px; align-items: center; }
.chip { min-height: 0; padding: 2px; border-width: 0; background: none; }
.chip .at { height: 24px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.note { margin: 0; color: var(--cv-muted); font-size: 14.5px; }
.quote { margin: 0; justify-self: start; max-width: 60ch; padding: 10px 16px; border-radius: 6px 22px 22px 22px; background: var(--cv-sand); font-size: 15px; }
.verdict { display: grid; gap: 8px; justify-items: stretch; }
.verdict.muted { margin: 0; color: var(--cv-muted); font-size: 14px; }
.coach { padding: 20px; border-radius: 28px; background: var(--cv-surface); }
.acts { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
@media (max-width: 1100px) {
  .item { grid-template-columns: 56px minmax(0, 1fr); }
  .verdict { grid-column: 2; }
}
@media (max-width: 720px) {
  .item { grid-template-columns: minmax(0, 1fr); padding: 16px; }
  .verdict { grid-column: auto; }
  .tick { width: 40px; height: 40px; font-size: 20px; }
  .ft { font-size: 18px; }
}
</style>
