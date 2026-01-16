<script setup lang="ts">
// Activity (DESIGN.md §3): "Who did what, and when?" The audit trail as a soft line per day, each entry a sentence with the actor's initials and the actor's
// words in bold; filters by action, person and claim; a "Record intact" check of the hash chain (and a way to run it
// again); export as CSV.
import type { TimelineItem } from '@nuxt/ui'
import type { AuditEntry, ChainStatus, Member } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayGroup, fmtTime, initials } from '~/utils/format'
import { refDebounced } from '@vueuse/core'
import { questionFor } from '~/utils/places'

useHead({ title: 'Activity · ClaimVoice' })
const clock = useDemoClock()
const entries = ref<AuditEntry[]>([])
const total = ref(0)
const pageNo = ref(1)
const chain = ref<ChainStatus | null>(null)
const verifying = ref(false)
const people = ref<Member[]>([])
const actor = ref('everyone')
const action = ref('all')
const target = ref('')
const targetD = refDebounced(target, 300)
const loading = ref(true)
const error = ref<string | null>(null)
const actions = [
  { value: 'all', label: 'Everything' }, { value: 'call.', label: 'Calls' }, { value: 'claim.', label: 'Claims and routes' },
  { value: 'check.', label: 'Routing checks' }, { value: 'qa.', label: 'Quality' }, { value: 'settings.', label: 'Settings' },
  { value: 'surge.', label: 'Surge' }, { value: 'auth.', label: 'Sign-ins' },
]
const personItems = computed(() => [{ value: 'everyone', label: 'Everyone' }, ...people.value.map(p => ({ value: p.userId, label: p.fullName }))])
const query = computed(() => ({
  action: action.value === 'all' ? undefined : action.value,
  actor: actor.value === 'everyone' ? undefined : actor.value,
  target: targetD.value || undefined,
}))

async function load(more = false) {
  loading.value = true
  error.value = null
  try {
    const p = await api.audit.list({ ...query.value, page: more ? pageNo.value + 1 : 1, pageSize: 50 })
    entries.value = more ? [...entries.value, ...p.items] : p.items
    total.value = p.total
    pageNo.value = p.page
  }
  catch (e) { error.value = (e as Error).message }
  loading.value = false
}
async function verify() {
  verifying.value = true
  try { chain.value = await api.audit.verify() }
  catch { /* the last result stays on screen */ }
  verifying.value = false
}
onMounted(async () => {
  void verify()
  people.value = await api.org.members().catch(() => [])
})
watch(query, () => load(), { immediate: true })

/** "Renée Kowalchuk took over Line 1 …": bold the actor and the action words. */
function parts(e: AuditEntry): { lead: string, rest: string } {
  const lead = `${e.actorLabel} ${e.actionLabel}`
  if (e.summary.startsWith(lead)) return { lead, rest: e.summary.slice(lead.length) }
  if (e.summary.startsWith(e.actorLabel)) return { lead: e.actorLabel, rest: e.summary.slice(e.actorLabel.length) }
  return { lead: '', rest: e.summary }
}
const groups = computed(() => {
  const out: { day: string, items: TimelineItem[] }[] = []
  for (const e of entries.value) {
    const day = fmtDayGroup(e.at, clock.now.value)
    const item: TimelineItem = { value: e.id, date: fmtTime(e.at), avatar: { text: initials(e.actorLabel), alt: e.actorLabel }, ...parts(e) }
    const g = out[out.length - 1]
    if (g && g.day === day) g.items.push(item)
    else out.push({ day, items: [item] })
  }
  return out
})
const exportUrl = computed(() => api.audit.exportUrl(query.value))
</script>

<template>
  <div>
    <PageHead :title="questionFor('activity')" :caption="`Every sensitive action at Larkspur Mutual, newest first${total ? `: ${total.toLocaleString('en-CA')} entries, each chained to the one before` : ''}.`">
      <UTooltip v-if="chain" :text="`${chain.checked} entries checked`">
        <CvTag :kind="chain.ok ? 'fast' : 'urgent'" :icon="chain.ok ? 'check' : 'urgent'" class="hide-phone">
          {{ chain.ok ? `Record intact · checked ${fmtTime(chain.checkedAt)}` : `Record broken at entry ${chain.firstBrokenSeq}` }}
        </CvTag>
      </UTooltip>
      <UButton color="neutral" variant="soft" icon="i-lucide-link-2" :loading="verifying" class="hide-phone" @click="verify">
        Verify the chain
      </UButton>
      <UButton :href="exportUrl" external download color="neutral" variant="soft" icon="i-lucide-download" class="hide-phone">
        Export CSV
      </UButton>
    </PageHead>

    <div class="filters">
      <USelectMenu v-model="action" :items="actions" value-key="value" :search-input="false" icon="i-lucide-list-filter" class="w-56" aria-label="Show by action" />
      <USelectMenu v-model="actor" :items="personItems" value-key="value" :search-input="{ placeholder: 'Find a person' }" icon="i-lucide-user-round" class="w-60" aria-label="Person" />
      <UInput v-model="target" type="search" icon="i-lucide-search" placeholder="Claim number or line" class="w-64" aria-label="Claim or line" />
    </div>

    <UAlert
      v-if="chain && !chain.ok" color="error" variant="soft" icon="i-lucide-triangle-alert" role="alert" class="broken"
      :title="`The record doesn't add up from entry ${chain.firstBrokenSeq}: ${chain.reason}. Tell your privacy officer.`"
    />
    <StateNote v-if="error" kind="error" class="mb-4" title="We couldn't load the activity." :body="error" retry @retry="load()" />

    <section v-for="(g, gi) in groups" :key="g.day" class="day" :aria-labelledby="`day-${gi}`">
      <h2 :id="`day-${gi}`">
        {{ g.day }}
      </h2>
      <UTimeline
        :items="g.items" color="neutral" size="md" class="log"
        :ui="{ indicator: 'bg-person-wash text-person font-round font-[900]', separator: 'bg-sunk-2 w-[3px] rounded-full', wrapper: 'pb-5 flex items-baseline gap-4', date: 'num text-[13px] font-medium text-muted shrink-0 w-[68px]', title: 'text-[15px] font-normal text-ink' }"
      >
        <template #title="{ item }">
          <p class="m-0">
            <b v-if="item.lead">{{ item.lead }}</b>{{ item.rest }}
          </p>
        </template>
      </UTimeline>
    </section>

    <div v-if="loading && !entries.length" class="day" aria-busy="true" aria-label="Loading the activity">
      <div v-for="n in 6" :key="n" class="flex items-center gap-3 py-2">
        <USkeleton class="size-8 rounded-full" /><USkeleton class="h-5 flex-1" />
      </div>
    </div>
    <StateNote v-else-if="!entries.length && !error" class="mb-4" title="Nothing matches." body="Try another person or action." />

    <div v-if="entries.length < total" class="more">
      <UButton color="neutral" variant="soft" icon="i-lucide-chevron-down" :loading="loading" @click="load(true)">
        Show older entries
      </UButton>
      <span class="text-muted text-sm num">{{ entries.length }} of {{ total }}</span>
    </div>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 0 0 20px; }
.broken { margin: 0 0 16px; width: auto; }
.day { padding: 22px 24px 8px; border-radius: 28px; background: var(--cv-surface); margin-bottom: 14px; box-shadow: var(--cv-shadow-soft); }
.day h2 { font-size: 24px; font-weight: 900; margin-bottom: 14px; }
.log { max-width: 980px; }
.log b { font-weight: 600; }
.more { display: flex; gap: 14px; align-items: center; padding: 8px 0 24px; }
@media (max-width: 720px) {
  .filters > * { width: 100%; }
  .day { padding: 16px 16px 4px; border-radius: 24px; }
}
</style>
