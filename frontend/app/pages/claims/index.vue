<script setup lang="ts">
// Claims: a register. The slate, the route filter (tabs) and search, then one table row per claim: number, caller,
// loss, place, reported, where it goes (icon + word), who has it and its state. A row opens the claim file. The
// filters and the search live in the URL (?route=, ?assigned=me, ?q=).
import type { TableColumn } from '@nuxt/ui'
import type { ClaimSummary, Page } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayShort, fmtTime, initials } from '~/utils/format'
import { lossIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'
import { refDebounced } from '@vueuse/core'

useHead({ title: 'Claims · ClaimVoice' })
const route = useRoute()
const router = useRouter()
const { can } = useSession()
const view = ref(route.query.assigned === 'me' ? 'mine' : String(route.query.route ?? 'all'))
const q = ref(String(route.query.q ?? ''))
const qd = refDebounced(q, 250)
const page = ref<Page<ClaimSummary> | null>(null)
const items = ref<ClaimSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const tabs = computed(() => [
  { value: 'all', label: 'All', icon: 'i-lucide-file-text' },
  { value: 'fast_track', label: 'Fast-track', icon: 'i-lucide-check' },
  { value: 'adjuster', label: 'Adjuster', icon: 'i-lucide-user-round' },
  ...(can('siu:read') ? [{ value: 'special_investigation', label: 'Closer look', icon: 'i-lucide-search' }] : []),
  { value: 'mine', label: 'Assigned to me', icon: 'i-lucide-user-round-check' },
])
const routeFilter = computed(() => (view.value === 'all' || view.value === 'mine' ? undefined : view.value))
const mine = computed(() => view.value === 'mine')

async function load(more = false) {
  loading.value = true
  error.value = null
  try {
    const next = await api.claims.list({ route: routeFilter.value, assigned: mine.value ? 'me' : undefined, q: qd.value || undefined, page: more && page.value ? page.value.page + 1 : 1, pageSize: 25 })
    page.value = next
    items.value = more ? [...items.value, ...next.items] : next.items
  }
  catch (e) { error.value = (e as Error).message }
  loading.value = false
}
watch([view, qd], () => {
  void router.replace({ query: { ...(routeFilter.value ? { route: routeFilter.value } : {}), ...(mine.value ? { assigned: 'me' } : {}), ...(qd.value ? { q: qd.value } : {}) } })
  void load()
}, { immediate: true })

const caption = computed(() => {
  if (!page.value) return ''
  const n = page.value.total
  const newOnes = items.value.filter(c => c.status === 'new').length
  const label = view.value !== 'all' ? tabs.value.find(p => p.value === view.value)?.label.toLowerCase() : null
  return `${n} claim${n === 1 ? '' : 's'}${label ? ` · ${label}` : ''}${newOnes ? ` · ${newOnes} waiting for a first look` : ''}`
})
// The register reads in the organisation's time (Calgary), so rows sort and compare at a glance.
const ORG_TIME = 'America/Edmonton'
const placeOf = (c: ClaimSummary) => (c.lossPlace ?? c.regionLabel)

const columns: TableColumn<ClaimSummary>[] = [
  { accessorKey: 'claimNumber', header: 'Claim' },
  { accessorKey: 'holderName', header: 'Caller' },
  { id: 'loss', header: 'What happened' },
  { id: 'place', header: 'Where', cell: ({ row }) => placeOf(row.original) },
  { id: 'reported', header: 'Reported' },
  { id: 'route', header: 'Where it goes' },
  { id: 'assigned', header: 'Assigned' },
  { id: 'status', header: 'State' },
]
function openClaim(row: { original: ClaimSummary }) { void navigateTo(`/claims/${row.original.id}`) }
const more = computed(() => (page.value && page.value.page < page.value.totalPages ? Math.min(25, page.value.total - items.value.length) : 0))
</script>

<template>
  <div>
    <Slate title="Claims" :caption="caption" />

    <div class="filters">
      <UTabs v-model="view" :items="tabs" :content="false" variant="pill" size="sm" color="neutral" aria-label="Show claims by route" class="tabs" />
      <UInput v-model="q" type="search" icon="i-lucide-search" placeholder="Claim number, name or place" aria-label="Find a claim" class="search" />
    </div>

    <StateNote v-if="error" kind="error" title="We couldn't load the claims." :body="error" retry class="m-4 sm:mx-8" @retry="load()" />

    <div v-if="loading && !items.length && !error" class="skel" aria-busy="true" aria-label="Loading the claims">
      <div v-for="n in 6" :key="n" class="srow">
        <USkeleton class="h-5 w-28" /><USkeleton class="h-5 w-40" /><USkeleton class="h-5 flex-1" /><USkeleton class="h-7 w-28 rounded-full" />
      </div>
    </div>

    <template v-else-if="items.length">
      <UTable :data="items" :columns="columns" class="tbl" :ui="{ tr: 'cursor-pointer hover:bg-sunk' }" aria-label="Claims" @select="openClaim">
        <template #claimNumber-cell="{ row }">
          <NuxtLink :to="`/claims/${row.original.id}`" class="font-semibold num" @click.stop>
            {{ row.original.claimNumber }}
          </NuxtLink>
        </template>
        <template #holderName-cell="{ row }">
          <span class="who" :lang="row.original.language === 'fr' ? 'fr' : undefined">{{ row.original.holderName }}</span>
          <UBadge v-if="row.original.language === 'fr'" color="primary" variant="soft" size="sm" class="ml-1.5">
            FR
          </UBadge>
        </template>
        <template #loss-cell="{ row }">
          <span class="loss"><UIcon :name="icon(lossIcon(row.original.lossType))" class="size-4 text-orchid-ink" />{{ row.original.lossTypeLabel }}</span>
        </template>
        <template #reported-cell="{ row }">
          <span class="when num">{{ fmtDayShort(row.original.reportedAt, ORG_TIME) }} <span>{{ fmtTime(row.original.reportedAt, ORG_TIME) }}</span></span>
        </template>
        <template #route-cell="{ row }">
          <span class="badges">
            <CvTag v-if="row.original.urgentSafety" kind="urgent" icon="urgent">Urgent safety</CvTag>
            <RouteTag v-if="row.original.route" :route="row.original.route.route" :label="row.original.route.label" />
            <RouteTag v-if="row.original.siuOpen && row.original.route?.route !== 'special_investigation'" route="special_investigation" />
            <CvTag v-if="row.original.route?.decidedBy === 'person'" kind="plain" icon="swap">Changed by a person</CvTag>
            <span v-if="!row.original.route" class="text-muted text-sm">Not routed yet</span>
          </span>
        </template>
        <template #assigned-cell="{ row }">
          <span v-if="row.original.assignedTo" class="person">
            <UAvatar :text="initials(row.original.assignedTo.name)" size="xs" class="bg-adj-wash text-adj font-bold" />{{ row.original.assignedTo.name }}
          </span>
          <span v-else class="text-muted">Not assigned yet</span>
        </template>
        <template #status-cell="{ row }">
          <span class="state">
            {{ row.original.statusLabel }}
            <span v-if="row.original.photos" class="ph" :aria-label="`${row.original.photos} photos`"><UIcon name="i-lucide-camera" class="size-3.5" />{{ row.original.photos }}</span>
          </span>
        </template>
      </UTable>
      <div v-if="more" class="more">
        <UButton color="neutral" variant="soft" :loading="loading" trailing-icon="i-lucide-chevron-down" @click="load(true)">
          Show {{ more }} more
        </UButton>
        <span class="text-muted text-sm num">{{ items.length }} of {{ page?.total }}</span>
      </div>
    </template>

    <StateNote v-else-if="!error" class="m-4 sm:mx-8" title="No claims match." body="Try another route, or clear the search." />
  </div>
</template>

<style scoped>
.filters { display: flex; align-items: center; gap: 12px 16px; flex-wrap: wrap; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.search { margin-left: auto; width: 320px; }
.tbl { border-bottom: 1px solid var(--cv-rule); }
.tbl :deep(th:first-child), .tbl :deep(td:first-child) { padding-left: 32px; }
.tbl :deep(th:last-child), .tbl :deep(td:last-child) { padding-right: 32px; }
.who { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 650; font-size: 16px; }
.loss, .person { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.when { white-space: nowrap; font-weight: 600; }
.when span { color: var(--cv-muted); font-weight: 500; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.state { display: inline-flex; align-items: center; gap: 8px; color: var(--cv-muted); font-weight: 600; white-space: nowrap; }
.ph { display: inline-flex; gap: 3px; align-items: center; font-size: 13px; }
.skel { display: grid; }
.srow { display: flex; align-items: center; gap: 20px; padding: 16px 32px; border-bottom: 1px solid var(--cv-rule); }
.more { display: flex; align-items: center; gap: 14px; padding: 16px 32px; }
@media (max-width: 720px) {
  .filters { padding: 12px 16px; }
  .tabs { width: 100%; overflow-x: auto; scrollbar-width: none; }
  .search { margin-left: 0; width: 100%; }
  .tbl { overflow-x: auto; }
  .tbl :deep(th:first-child), .tbl :deep(td:first-child) { padding-left: 16px; }
  .srow, .more { padding-left: 16px; padding-right: 16px; }
}
</style>
