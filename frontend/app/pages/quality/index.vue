<script setup lang="ts">
// Call quality: the review queue (flagged calls first) with rubric beads and filter pills, and the review beside it.
// Opening a call jumps its recording to the flagged moment. Desktop shows the queue and the review side by side.
import type { Page, QaQueueItem } from '~/types/api'
import { api } from '~/utils/api'
import { fmtClock, fmtDayShort, fmtTime } from '~/utils/format'

useHead({ title: 'Quality · ClaimVoice' })
const route = useRoute()
const router = useRouter()
const status = ref(String(route.query.status ?? 'needs_review'))
const item = ref(String(route.query.item ?? ''))
const page = ref<Page<QaQueueItem> | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)
const selected = computed(() => (typeof route.query.call === 'string' ? route.query.call : page.value?.items[0]?.callId ?? null))

const filters = [
  { key: '', label: 'Everything flagged' },
  { key: 'consent_first', label: 'Missed consent' },
  { key: 'handoff_correct', label: 'Late hand-off' },
  { key: 'no_card_numbers', label: 'Card number' },
  { key: 'required_fields', label: 'Low details' },
]

async function load() {
  loading.value = true
  error.value = null
  try { page.value = await api.qa.queue({ status: status.value, item: item.value || undefined, pageSize: 50 }) }
  catch (e) { error.value = (e as Error).message }
  loading.value = false
}
watch([status, item], () => {
  void router.replace({ query: { ...(status.value !== 'needs_review' ? { status: status.value } : {}), ...(item.value ? { item: item.value } : {}) } })
  void load()
}, { immediate: true })

const caption = computed(() => {
  const n = page.value?.total ?? 0
  if (status.value === 'reviewed') return `${n} reviewed this month`
  return n ? `${n} call${n === 1 ? '' : 's'} to review · flagged first, then the lowest scores` : 'Every call this week met the rubric'
})
function open(c: QaQueueItem) { void router.replace({ query: { ...route.query, call: c.callId } }) }
function next() {
  const items = page.value?.items ?? []
  const i = items.findIndex(x => x.callId === selected.value)
  const n = items[i + 1] ?? items[0]
  if (n) open(n)
  void load()
}
</script>

<template>
  <div>
    <PageHeader title="Quality" :caption="caption">
      <div class="seg" role="group" aria-label="Which calls">
        <button type="button" :aria-pressed="status === 'needs_review'" @click="status = 'needs_review'">
          To review
        </button>
        <button type="button" :aria-pressed="status === 'reviewed'" @click="status = 'reviewed'">
          Reviewed
        </button>
      </div>
    </PageHeader>
    <div class="layout">
      <aside class="queue" aria-label="Review queue">
        <div class="pills" role="group" aria-label="Filter by what was missed">
          <button v-for="f in filters" :key="f.key" type="button" class="pill" :aria-pressed="item === f.key" @click="item = f.key">
            {{ f.label }}
          </button>
        </div>
        <StateNote v-if="error" kind="error" title="We couldn't load the queue." :body="error" retry @retry="load" />
        <div v-else-if="loading && !page" class="rows" aria-busy="true">
          <div v-for="n in 4" :key="n" class="row skel">
            <span class="skeleton" style="width: 60%; height: 18px" />
            <div class="bs">
              <span v-for="b in 6" :key="b" class="skeleton" style="width: 70px; height: 24px" />
            </div>
          </div>
        </div>
        <StateNote v-else-if="!page?.items.length" title="Nothing to review." body="Every call this week met the rubric." />
        <ol v-else class="rows">
          <li v-for="c in page.items" :key="c.callId">
            <button type="button" class="row" :aria-current="selected === c.callId ? 'true' : undefined" @click="open(c)">
              <span class="top">
                <b>{{ c.callerLabel }}</b>
                <span class="band" :class="c.band"><CvIcon :name="c.band === 'good' ? 'check' : c.band === 'failed' ? 'urgent' : 'clock'" size="s" />{{ c.bandLabel }}</span>
              </span>
              <span class="sub num">{{ c.claimNumber ?? c.reference }} · {{ c.lineLabel ? `${c.lineLabel} · ` : '' }}{{ fmtDayShort(c.startedAt) }}, {{ fmtTime(c.startedAt) }} · {{ fmtClock(c.durationSeconds) }}</span>
              <span class="why">{{ c.reasonQueued }}</span>
              <RubricBeads :beads="c.beads" small />
              <span class="rev">{{ c.reviewer ? `Reviewer: ${c.reviewer.name}` : 'Not reviewed yet' }}</span>
            </button>
          </li>
        </ol>
      </aside>
      <ReviewPanel v-if="selected" :key="selected" :call-id="selected" class="review" @done="next" />
    </div>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 420px minmax(0, 1fr); gap: 16px; margin: 0 32px; align-items: start; }
.queue { display: grid; gap: 10px; position: sticky; top: 12px; max-height: calc(100dvh - 130px); overflow: auto; padding-bottom: 8px; scrollbar-width: thin; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { height: 34px; padding: 0 12px; border-radius: 999px; border: 0; background: var(--cv-sunk); font-weight: 650; font-size: 13px; color: var(--cv-muted); }
.pill[aria-pressed="true"] { background: var(--cv-ink); color: var(--cv-bg); }
.rows { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.row { width: 100%; border: 0; text-align: left; background: var(--cv-surface); border-radius: 20px; padding: 12px 14px; display: grid; gap: 6px; color: var(--cv-ink); }
.row:hover { box-shadow: inset 0 0 0 1.5px var(--cv-orchid-wash); }
.row[aria-current="true"] { box-shadow: inset 0 0 0 2.5px var(--cv-orchid); }
.row.skel .bs { display: flex; gap: 5px; flex-wrap: wrap; }
.top { display: flex; align-items: center; gap: 8px; }
.top b { font-family: var(--font-display); font-size: 17px; font-weight: 700; letter-spacing: -0.02em; }
.band { margin-left: auto; display: inline-flex; gap: 4px; align-items: center; font-size: 12.5px; font-weight: 700; }
.band.failed { color: var(--cv-urgent); } .band.needs_attention { color: var(--cv-siu); } .band.good { color: var(--cv-fast); }
.sub, .rev { color: var(--cv-muted); font-size: 12.5px; }
.why { font-size: 13.5px; font-weight: 600; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } .queue { position: static; max-height: none; } }
@media (max-width: 720px) { .layout { margin: 0 16px; } }
</style>
