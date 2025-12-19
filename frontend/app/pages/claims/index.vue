<script setup lang="ts">
// Claims: a ledger of rounded rows with filter pills by route. Every row says where the claim goes, in words.
import type { ClaimSummary, Page } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayShort, fmtTime, initials } from '~/utils/format'
import { lossIcon } from '~/utils/labels'
import { refDebounced } from '@vueuse/core'

useHead({ title: 'Claims · ClaimVoice' })
const route = useRoute()
const router = useRouter()
const { can } = useSession()
const filter = ref(String(route.query.route ?? 'all'))
const mine = ref(route.query.assigned === 'me')
const q = ref(String(route.query.q ?? ''))
const qd = refDebounced(q, 250)
const page = ref<Page<ClaimSummary> | null>(null)
const items = ref<ClaimSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const pills = computed(() => [
  { key: 'all', label: 'All claims', icon: 'doc' },
  { key: 'fast_track', label: 'Fast-track', icon: 'check' },
  { key: 'adjuster', label: 'Adjuster', icon: 'person' },
  ...(can('siu:read') ? [{ key: 'special_investigation', label: 'Closer look', icon: 'look' }] : []),
])

async function load(more = false) {
  loading.value = true
  error.value = null
  try {
    const next = await api.claims.list({ route: filter.value === 'all' ? undefined : filter.value, assigned: mine.value ? 'me' : undefined, q: qd.value || undefined, page: more && page.value ? page.value.page + 1 : 1, pageSize: 25 })
    page.value = next
    items.value = more ? [...items.value, ...next.items] : next.items
  }
  catch (e) { error.value = (e as Error).message }
  loading.value = false
}
watch([filter, mine, qd], () => {
  void router.replace({ query: { ...(filter.value !== 'all' ? { route: filter.value } : {}), ...(mine.value ? { assigned: 'me' } : {}), ...(qd.value ? { q: qd.value } : {}) } })
  void load()
}, { immediate: true })

const caption = computed(() => {
  if (!page.value) return ''
  const n = page.value.total
  const newOnes = items.value.filter(c => c.status === 'new').length
  return `${n} claim${n === 1 ? '' : 's'}${filter.value !== 'all' ? ` · ${pills.value.find(p => p.key === filter.value)?.label.toLowerCase()}` : ''}${newOnes ? ` · ${newOnes} waiting for a first look` : ''}`
})
// The ledger reads in the organisation's time (Calgary), so rows sort and compare at a glance.
const ORG_TIME = 'America/Edmonton'
</script>

<template>
  <div>
    <PageHeader title="Claims" :caption="caption" />
    <div class="filters">
      <div class="pills" role="group" aria-label="Show claims by route">
        <button v-for="p in pills" :key="p.key" type="button" class="pill" :aria-pressed="filter === p.key" @click="filter = p.key">
          <CvIcon :name="p.icon" size="s" />{{ p.label }}
        </button>
        <button type="button" class="pill" :aria-pressed="mine" @click="mine = !mine">
          <CvIcon name="person" size="s" />Assigned to me
        </button>
      </div>
      <label class="search">
        <CvIcon name="search" size="s" /><span class="sr-only-cv">Find a claim</span>
        <input v-model="q" type="search" placeholder="Claim number, name or place">
      </label>
    </div>

    <StateNote v-if="error" kind="error" title="We couldn't load the claims." :body="error" retry class="wrap" @retry="load()" />
    <ol v-if="items.length" class="ledger" aria-label="Claims">
      <li v-for="c in items" :key="c.id">
        <NuxtLink class="row" :to="`/claims/${c.id}`">
          <span class="ic"><CvIcon :name="lossIcon(c.lossType)" /></span>
          <span class="who">
            <b>{{ c.holderName }}</b>
            <span class="num">{{ c.claimNumber }} · {{ c.lossTypeLabel }}{{ c.lossPlace ? `, ${c.lossPlace}` : '' }}</span>
          </span>
          <span class="when">
            <time class="num">{{ fmtDayShort(c.reportedAt, ORG_TIME) }}</time>
            <span class="num">{{ fmtTime(c.reportedAt, ORG_TIME) }}</span>
          </span>
          <span class="tags">
            <CvTag v-if="c.urgentSafety" kind="urgent" icon="urgent">Urgent safety</CvTag>
            <RouteTag v-if="c.route" :route="c.route.route" :label="c.route.label" />
            <RouteTag v-if="c.siuOpen && c.route?.route !== 'special_investigation'" route="special_investigation" />
            <CvTag v-if="c.route?.decidedBy === 'person'" kind="plain" icon="swap">Changed by a person</CvTag>
          </span>
          <span class="status">{{ c.statusLabel }}</span>
          <span class="meta">
            <span v-if="c.photos" class="ph" :title="`${c.photos} photos`"><CvIcon name="camera" size="s" />{{ c.photos }}</span>
            <span v-if="c.assignedTo" class="avatar sm" :title="c.assignedTo.name">{{ initials(c.assignedTo.name) }}</span>
            <span v-else class="avatar sm none" title="Not assigned yet">·</span>
          </span>
        </NuxtLink>
      </li>
    </ol>
    <div v-else-if="loading" class="ledger" aria-busy="true">
      <span v-for="n in 6" :key="n" class="skeleton" style="display:block; height: 64px; border-radius: 14px; margin-bottom: 8px" />
    </div>
    <StateNote v-else-if="!error" class="wrap" title="No claims match." body="Try another route, or clear the search." />
    <div v-if="page && page.page < page.totalPages" class="more">
      <button class="btn soft" type="button" :disabled="loading" @click="load(true)">
        Show {{ Math.min(25, page.total - items.length) }} more
      </button>
    </div>
  </div>
</template>

<style scoped>
.filters { display: flex; align-items: center; gap: 12px; margin: 0 32px 14px; flex-wrap: wrap; }
.pills { display: flex; gap: 6px; flex-wrap: wrap; }
.pill { display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 14px; border-radius: 999px; border: 0; background: var(--cv-sunk); font-weight: 650; font-size: 14px; color: var(--cv-muted); }
.pill:hover { color: var(--cv-ink); }
.pill[aria-pressed="true"] { background: var(--cv-ink); color: var(--cv-bg); }
.search { margin-left: auto; display: flex; align-items: center; gap: 8px; height: 42px; padding: 0 16px; border-radius: 999px; background: var(--cv-surface); box-shadow: inset 0 0 0 1.5px var(--cv-sunk-2); color: var(--cv-muted); min-width: 280px; }
.search input { border: 0; background: transparent; font: inherit; font-size: 14.5px; color: var(--cv-ink); flex: 1; min-width: 0; }
.search input:focus { outline: none; }
.search:focus-within { box-shadow: inset 0 0 0 2.5px var(--cv-orchid); }
.ledger { list-style: none; margin: 0 32px; padding: 0; display: grid; gap: 8px; }
.row { display: grid; grid-template-columns: 44px minmax(0, 1.6fr) 110px minmax(0, 1.6fr) 120px 90px; gap: 14px; align-items: center; background: var(--cv-surface); border-radius: 14px; padding: 10px 16px 10px 10px; text-decoration: none; color: inherit; min-height: 64px; }
.row:hover { box-shadow: inset 0 0 0 1.5px var(--cv-orchid-wash); }
.ic { width: 44px; height: 44px; border-radius: 50%; background: var(--cv-sunk); display: grid; place-items: center; color: var(--cv-orchid-ink); }
.who { display: grid; min-width: 0; }
.who b { font-family: var(--font-display); font-size: 17px; font-weight: 700; letter-spacing: -0.02em; }
.who span, .when span { color: var(--cv-muted); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.when { display: grid; font-size: 14px; font-weight: 650; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.status { font-size: 13.5px; color: var(--cv-muted); font-weight: 600; }
.meta { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.ph { display: inline-flex; gap: 4px; align-items: center; color: var(--cv-muted); font-size: 13px; font-weight: 650; }
.avatar.sm { width: 32px; height: 32px; font-size: 11.5px; }
.avatar.none { background: var(--cv-sunk); color: var(--cv-faint); }
.more { display: flex; justify-content: center; margin: 18px 0 0; }
.wrap { margin: 0 32px; }
@media (max-width: 1100px) { .row { grid-template-columns: 44px minmax(0, 1fr) minmax(0, 1fr) 70px; } .when, .status { display: none; } }
@media (max-width: 720px) {
  .filters, .ledger, .wrap { margin-left: 16px; margin-right: 16px; }
  .search { min-width: 0; width: 100%; margin: 0; }
  .pills { overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; width: 100%; }
  .pill { flex: none; }
  .row { grid-template-columns: 40px minmax(0, 1fr) auto; gap: 10px; }
  .ic { width: 40px; height: 40px; }
  .tags { grid-column: 2 / -1; }
  .meta { grid-row: 1; grid-column: 3; }
}
</style>
