<script setup lang="ts">
// Call quality: the review queue as a register, flagged calls first, with the rubric beads as a column and what was
// missed as tabs. A row opens its review, where the recording jumps to the flagged moment. Filters live in the URL
// (?status=, ?item=); an old ?call= link opens that review.
import type { TableColumn } from '@nuxt/ui'
import type { Page, QaQueueItem } from '~/types/api'
import { api } from '~/utils/api'
import { fmtClock, fmtDayShort, fmtTime } from '~/utils/format'

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
  if (status.value === 'reviewed') return `${n} reviewed this month`
  return n ? `${n} call${n === 1 ? '' : 's'} to review · flagged first, then the lowest scores` : 'Every call this week met the rubric'
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
    <Slate title="Quality" :caption="caption">
      <UTabs v-model="status" :items="statuses" :content="false" variant="pill" size="sm" color="neutral" aria-label="Which calls" />
    </Slate>

    <div class="filters">
      <UTabs v-model="item" :items="filters" :content="false" variant="link" size="sm" color="neutral" aria-label="Filter by what was missed" class="tabs" />
    </div>

    <StateNote v-if="error" kind="error" title="We couldn't load the queue." :body="error" retry class="m-4 sm:mx-8" @retry="load" />

    <div v-else-if="loading && !page" class="skel" aria-busy="true" aria-label="Loading the queue">
      <div v-for="n in 4" :key="n" class="srow">
        <USkeleton class="h-5 w-40" />
        <div class="flex flex-wrap gap-1.5 flex-1">
          <USkeleton v-for="b in 6" :key="b" class="h-6 w-20 rounded-full" />
        </div>
      </div>
    </div>

    <StateNote v-else-if="!page?.items.length" class="m-4 sm:mx-8" title="Nothing to review." body="Every call this week met the rubric." />

    <UTable v-else :data="page.items" :columns="columns" class="tbl" :ui="{ tr: 'cursor-pointer hover:bg-sunk', td: 'align-top' }" aria-label="Review queue" @select="open">
      <template #callerLabel-cell="{ row }">
        <NuxtLink :to="hrefOf(row.original)" class="who" @click.stop>
          {{ row.original.callerLabel }}
        </NuxtLink>
        <span class="why">{{ row.original.reasonQueued }}</span>
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
.filters { padding: 6px 32px 0; border-bottom: 1px solid var(--cv-rule); overflow-x: auto; scrollbar-width: none; }
.tbl { border-bottom: 1px solid var(--cv-rule); }
.tbl :deep(th:first-child), .tbl :deep(td:first-child) { padding-left: 32px; }
.tbl :deep(th:last-child), .tbl :deep(td:last-child) { padding-right: 32px; }
.who { display: block; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 660; font-size: 16.5px; color: inherit; text-decoration: none; }
.who:hover { text-decoration: underline; text-underline-offset: 3px; }
.why { display: block; font-size: 13.5px; font-weight: 600; margin-top: 2px; white-space: normal; max-width: 34ch; }
.sub { display: block; color: var(--cv-muted); font-size: 12.5px; margin-top: 3px; }
.nowrap { white-space: nowrap; }
.beads { max-width: 460px; }
.skel { display: grid; }
.srow { display: flex; align-items: center; gap: 20px; padding: 16px 32px; border-bottom: 1px solid var(--cv-rule); }
@media (max-width: 720px) {
  .filters { padding: 4px 16px 0; }
  .tbl { overflow-x: auto; }
  .tbl :deep(th:first-child), .tbl :deep(td:first-child) { padding-left: 16px; }
  .srow { padding-left: 16px; padding-right: 16px; }
}
</style>
