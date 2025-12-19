<script setup lang="ts">
// The review: the recording opened at the flagged moment, rubric beads pinned where each item was judged, the
// transcript around that moment, Agree / Disagree per item, and a coaching note for the script owner.
import type { CallDetail, QaScore, Recording, Transcript } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, fmtDayShort, fmtTime } from '~/utils/format'
import { beadIcon } from '~/utils/labels'
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
const verdicts = ref<Record<string, 'agree' | 'disagree'>>({})
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
    for (const it of s.items) if (it.reviewerVerdict) verdicts.value[it.key] = it.reviewerVerdict
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
const pins = computed<ExtraPin[]>(() => (score.value?.items ?? []).filter(i => i.atSeconds != null && i.passed === false).map(i => ({ atSeconds: i.atSeconds!, label: i.label, kind: 'fail' })))
const around = computed(() => {
  const turns = transcript.value?.turns ?? []
  const ms = (score.value?.focus?.atSeconds ?? t.value) * 1000
  const i = Math.max(0, turns.findIndex(x => x.endMs >= ms))
  return turns.slice(Math.max(0, i - 2), i + 4)
})
const ms = computed(() => t.value * 1000)

async function submit() {
  if (!score.value) return
  saving.value = true
  try {
    score.value = await api.qa.review(props.callId, {
      items: items.value.map(i => ({ key: i.key, verdict: verdicts.value[i.key] ?? 'agree', note: notes.value[i.key] || null })),
      coachingNote: coaching.value.trim() || null,
    })
    saved.value = true
  }
  catch (e) { error.value = e instanceof ApiError ? e.message : 'That review didn\'t save. Try again.' }
  saving.value = false
}
</script>

<template>
  <section class="panel" aria-label="Review">
    <StateNote v-if="error" kind="error" title="We couldn't open this review." :body="error" retry @retry="load" />
    <template v-if="score && call">
      <header class="head">
        <div>
          <h2>{{ call.callerLabel }}</h2>
          <p class="sub num">
            {{ score.claimNumber ?? call.reference }} · {{ fmtDayShort(call.startedAt) }}, {{ fmtTime(call.startedAt) }} · {{ call.lossTypeLabel ?? call.outcomeLabel }}
          </p>
        </div>
        <span class="score" :class="score.band"><CvIcon :name="score.band === 'good' ? 'check' : score.band === 'failed' ? 'urgent' : 'clock'" size="s" />{{ score.bandLabel }} · {{ Math.round(score.score) }} of 100</span>
      </header>
      <RubricBeads :beads="score.beads" />
      <p v-if="score.focus" class="focus">
        <CvIcon name="flag" size="s" />{{ score.focus.text }}
      </p>
      <CallRecording v-if="recording" ref="rec" :recording="recording" :caller-label="firstName(call.callerLabel)" :start-at="score.focus?.atSeconds ?? null" :extra-pins="pins" @time="x => (t = x)" />
      <div v-if="around.length" class="around">
        <div class="group-label">
          Around this moment
        </div>
        <div v-for="x in around" :key="x.id" class="t" :class="[x.speaker, { on: ms >= x.atMs && ms < x.endMs + 400 }]">
          <button type="button" class="tm num" @click="rec?.seek(x.atMs / 1000, true)">
            {{ fmtClock(x.atMs / 1000) }}
          </button>
          <div><b>{{ x.speaker === 'caller' ? firstName(x.speakerLabel) : x.speakerLabel }}</b><p><TranscriptText :text="x.text" :turn-id="x.id" /></p></div>
        </div>
      </div>
      <div class="items">
        <div class="group-label">
          Each item, and whether you agree
        </div>
        <div v-for="i in items" :key="i.key" class="item" :class="i.passed ? 'ok' : 'miss'">
          <div class="ih">
            <span class="mk"><CvIcon :name="i.passed ? 'check' : 'x'" size="s" /></span>
            <b><CvIcon :name="beadIcon(i.key)" size="s" />{{ i.label }}</b>
            <button v-if="i.atSeconds != null" class="heard chip" type="button" @click="rec?.seek(i.atSeconds!, true)">
              <span class="at"><CvIcon name="play" size="s" />{{ fmtClock(i.atSeconds) }}</span>
            </button>
            <div v-if="can('qa:review')" class="seg verdict" role="group" :aria-label="`Do you agree: ${i.label}`">
              <button type="button" :aria-pressed="(verdicts[i.key] ?? (score.status === 'reviewed' ? null : 'agree')) === 'agree'" @click="verdicts[i.key] = 'agree'">
                Agree
              </button>
              <button type="button" :aria-pressed="verdicts[i.key] === 'disagree'" @click="verdicts[i.key] = 'disagree'">
                Disagree
              </button>
            </div>
          </div>
          <p class="note">
            {{ i.note }}
          </p>
          <p v-for="(ev, k) in i.evidence" :key="k" class="quote">
            “{{ ev.quote }}”
          </p>
          <input v-if="verdicts[i.key] === 'disagree'" v-model="notes[i.key]" class="field-input sm" :aria-label="`Why you disagree: ${i.label}`" placeholder="Why you disagree, in a line">
        </div>
      </div>
      <div v-if="can('qa:review')" class="coach">
        <label for="coach">Coaching note to the script owner (optional)</label>
        <textarea id="coach" v-model="coaching" class="field-input" maxlength="600" placeholder="Acknowledge an injury before asking about the damage." />
        <div class="acts">
          <button class="btn primary" type="button" :disabled="saving" @click="saved ? emit('done') : submit()">
            {{ saved ? 'Next call' : 'Done' }}<CvIcon name="right" size="s" />
          </button>
          <span v-if="saved" class="tag fast"><CvIcon name="check" size="s" />Review saved and logged</span>
          <span v-else-if="score.reviewedBy" class="tag plain"><CvIcon name="check" size="s" />Reviewed by {{ score.reviewedBy.name }}</span>
        </div>
      </div>
    </template>
    <div v-else-if="!error" class="loading" aria-busy="true">
      <span class="skeleton" style="height: 34px; width: 50%" />
      <span class="skeleton" style="height: 28px" />
      <span class="skeleton" style="height: 150px; border-radius: 28px" />
    </div>
  </section>
</template>

<style scoped>
.panel { display: grid; gap: 12px; min-width: 0; }
.head { display: flex; align-items: flex-start; gap: 12px; }
h2 { font-size: 28px; font-weight: 750; letter-spacing: -0.03em; }
.sub { margin: 2px 0 0; color: var(--cv-muted); font-size: 14px; }
.score { margin-left: auto; display: inline-flex; gap: 6px; align-items: center; font-weight: 700; font-size: 14px; padding: 6px 14px; border-radius: 999px; background: var(--cv-surface); white-space: nowrap; }
.score.failed { color: var(--cv-urgent); } .score.needs_attention { color: var(--cv-siu); } .score.good { color: var(--cv-fast); }
.focus { margin: 0; display: flex; gap: 8px; align-items: center; font-family: var(--font-display); font-size: 19px; font-weight: 600; letter-spacing: -0.015em; color: var(--cv-orchid-ink); }
.around { background: var(--cv-surface); border-radius: 28px; padding: 14px 16px; display: grid; gap: 2px; }
.t { display: grid; grid-template-columns: 40px 1fr; gap: 8px; padding: 6px 10px; border-radius: 14px; font-size: 14.5px; }
.t.on { background: var(--cv-orchid-wash); }
.t b { display: block; font-size: 12px; color: var(--cv-muted); }
.t p { margin: 0; } .t.caller p { color: var(--cv-caller); }
.tm { border: 0; background: none; color: var(--cv-faint); font-size: 12px; font-weight: 650; padding: 2px 0 0; text-align: left; align-self: start; }
.items { display: grid; gap: 8px; }
.item { background: var(--cv-surface); border-radius: 20px; padding: 12px 14px; display: grid; gap: 6px; }
.ih { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ih b { display: inline-flex; gap: 6px; align-items: center; font-size: 15px; }
.mk { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; }
.ok .mk { background: var(--cv-fast-wash); color: var(--cv-fast); }
.miss .mk { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.verdict { margin-left: auto; }
.note { margin: 0; color: var(--cv-muted); font-size: 14px; }
.quote { margin: 0; font-family: var(--font-display); font-size: 15.5px; font-weight: 550; color: var(--cv-caller); }
.coach { display: grid; gap: 8px; }
.coach label { font-size: 13px; font-weight: 700; color: var(--cv-muted); }
.acts { display: flex; align-items: center; gap: 10px; }
.loading { display: grid; gap: 12px; }
</style>
