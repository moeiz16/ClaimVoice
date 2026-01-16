<script setup lang="ts">
// Quality (DESIGN.md §3): "Which calls missed the mark?" answered in a sentence, then the review queue as pebble rows,
// flagged calls first, with the rubric beads as a column and what was missed as filter pebbles. A row opens its review, where the recording jumps to the flagged moment. Filters live in the URL
// (?status=, ?item=); an old ?call= link opens that review.
import type { TableColumn } from '@nuxt/ui'
import type { Page, QaQueueItem } from '~/types/api'
import { api } from '~/utils/api'
import { fmtClock, fmtDayShort, fmtTime, initials } from '~/utils/format'
import { questionFor } from '~/utils/places'

definePageMeta({
  middleware: [(to) => {
    const { call, ...rest } = to.query
    if (typeof call === 'string' && call) return navigateTo({ path: `/quality/${call}`, query: rest }, { replace: true })
  }],
})
useHead({ title: 'Quality · ClaimVoice' })
const route = useRoute()
const router = useRouter()
const status = ref(String(route.query.status ?? 'needs_review'))
const item = ref(String(route.query.item ?? 'all'))
const page = ref<Page<QaQueueItem> | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)

const statuses = [{ value: 'needs_review', label: 'To review' }, { value: 'reviewed', label: 'Reviewed' }]
const filters = [
  { value: 'all', label: 'Everything flagged' },
  { value: 'consent_first', label: 'Missed consent' },
  { value: 'handoff_correct', label: 'Late hand-off' },
  { value: 'no_card_numbers', label: 'Card number' },
  { value: 'required_fields', label: 'Low details' },
]
const query = computed(() => ({ ...(status.value !== 'needs_review' ? { status: status.value } : {}), ...(item.value !== 'all' ? { item: item.value } : {}) }))

async function load() {
  loading.value = true
  error.value = null
  try { page.value = await api.qa.queue({ status: status.value, item: item.value === 'all' ? undefined : item.value, pageSize: 50 }) }
  catch (e) { error.value = (e as Error).message }
  loading.value = false
}
watch([status, item], () => {
  void router.replace({ query: query.value })
  void load()
}, { immediate: true })

const caption = computed(() => {
  const n = page.value?.total ?? 0
  if (status.value === 'reviewed') return `${n} call${n === 1 ? '' : 's'} reviewed this month.`
  return n ? `${n} call${n === 1 ? '' : 's'} to review: the flagged ones first, then the lowest scores.` : 'None. Every call this week met the rubric.'
})
const BAND = { good: { kind: 'fast', icon: 'check' }, needs_attention: { kind: 'siu', icon: 'clock' }, failed: { kind: 'urgent', icon: 'urgent' } } as const
const columns: TableColumn<QaQueueItem>[] = [
  { accessorKey: 'callerLabel', header: 'Caller' },
  { id: 'claim', header: 'Claim' },
  { id: 'when', header: 'When' },
  { id: 'band', header: 'Score' },
  { id: 'rubric', header: 'Rubric' },
  { id: 'reviewer', header: 'Reviewer' },
]
const hrefOf = (c: QaQueueItem) => ({ path: `/quality/${c.callId}`, query: query.value })
function open(row: { original: QaQueueItem }) { void navigateTo(hrefOf(row.original)) }
</script>

<template>
  <div>
    <PageHead :title="questionFor('quality')" :caption="caption">
      <UTabs v-model="status" :items="statuses" :content="false" size="sm" color="neutral" aria-label="Which calls" />
    </PageHead>

    <div class="filters">
      <UTabs v-model="item" :items="filters" :content="false" size="sm" color="neutral" aria-label="Filter by what was missed" class="tabs" :ui="{ list: 'bg-transparent p-0 gap-1.5', trigger: 'ring-2 ring-inset ring-rule data-[state=active]:ring-jade data-[state=active]:bg-jade-wash data-[state=active]:text-jade-ink', indicator: 'hidden' }" />
    </div>

    <StateNote v-if="error" kind="error" title="We couldn't load the queue." :body="error" retry class="mb-4" @retry="load" />

    <div v-else-if="loading && !page" class="skel" aria-busy="true" aria-label="Loading the queue">
      <USkeleton v-for="n in 4" :key="n" class="h-20 w-full rounded-[18px]" />
    </div>

    <StateNote v-else-if="!page?.items.length" class="mb-4" title="Nothing to review." body="Every call this week met the rubric." />

    <UTable v-else :data="page.items" :columns="columns" class="tbl" :ui="{ tr: 'cursor-pointer', td: 'align-top whitespace-normal' }" aria-label="Review queue" @select="open">
      <template #callerLabel-cell="{ row }">
        <span class="whorow">
          <span class="face" aria-hidden="true">{{ initials(row.original.callerLabel) }}</span>
          <span>
            <NuxtLink :to="hrefOf(row.original)" class="who" @click.stop>{{ row.original.callerLabel }}</NuxtLink>
            <span class="why">{{ row.original.reasonQueued }}</span>
          </span>
        </span>
      </template>
      <template #claim-cell="{ row }">
        <span class="num font-semibold">{{ row.original.claimNumber ?? row.original.reference }}</span>
        <span v-if="row.original.lineLabel" class="sub">{{ row.original.lineLabel }}</span>
      </template>
      <template #when-cell="{ row }">
        <span class="num nowrap">{{ fmtDayShort(row.original.startedAt) }}, {{ fmtTime(row.original.startedAt) }}</span>
        <span class="sub num">{{ fmtClock(row.original.durationSeconds) }} long</span>
      </template>
      <template #band-cell="{ row }">
        <CvTag :kind="BAND[row.original.band].kind" :icon="BAND[row.original.band].icon">
          {{ row.original.bandLabel }}
        </CvTag>
        <span class="sub num">{{ Math.round(row.original.score) }} of 100</span>
      </template>
      <template #rubric-cell="{ row }">
        <RubricBeads :beads="row.original.beads" small class="beads" />
      </template>
      <template #reviewer-cell="{ row }">
        <span :class="{ 'text-muted': !row.original.reviewer }" class="nowrap">{{ row.original.reviewer ? row.original.reviewer.name : 'Not reviewed yet' }}</span>
      </template>
    </UTable>
  </div>
</template>

<style scoped>
.filters { margin: 0 0 12px; overflow-x: auto; scrollbar-width: none; }
.whorow { display: flex; gap: 12px; align-items: flex-start; }
.face { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--cv-sand); color: var(--cv-caller); font-family: var(--font-round); font-weight: 900; font-size: 13px; }
.who { display: block; font-family: var(--font-round); font-weight: 850; font-size: 17px; color: inherit; text-decoration: none; }
.who:hover { text-decoration: underline; text-decoration-color: var(--cv-seaglass); text-decoration-thickness: 3px; text-underline-offset: 4px; }
.why { display: block; font-size: 13.5px; color: var(--cv-urgent); font-weight: 500; margin-top: 2px; white-space: normal; max-width: 34ch; }
.sub { display: block; color: var(--cv-muted); font-size: 12.5px; margin-top: 3px; }
.nowrap { white-space: nowrap; }
.beads { max-width: 460px; }
.skel { display: grid; gap: 8px; }
</style>
