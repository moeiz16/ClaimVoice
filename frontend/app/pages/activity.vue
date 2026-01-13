<script setup lang="ts">
// Activity: the audit trail as a timeline per day, each entry a sentence with the actor's initials and the actor's
// words in bold; filters by action, person and claim; a "Record intact" check of the hash chain (and a way to run it
// again); export as CSV.
import type { TimelineItem } from '@nuxt/ui'
import type { AuditEntry, ChainStatus, Member } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDayGroup, fmtTime, initials } from '~/utils/format'
import { refDebounced } from '@vueuse/core'

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
    <Slate title="Activity log" :caption="`Every sensitive action at Larkspur Mutual, newest first${total ? ` · ${total} entries` : ''}`">
      <UTooltip v-if="chain" :text="`${chain.checked} entries checked`">
        <CvTag :kind="chain.ok ? 'fast' : 'urgent'" :icon="chain.ok ? 'check' : 'urgent'" class="hide-phone">
          {{ chain.ok ? `Record intact ✓ · checked ${fmtTime(chain.checkedAt)}` : `Record broken at entry ${chain.firstBrokenSeq}` }}
        </CvTag>
      </UTooltip>
      <UButton color="neutral" variant="soft" icon="i-lucide-link-2" :loading="verifying" class="hide-phone" @click="verify">
        Verify the chain
      </UButton>
      <UButton :href="exportUrl" external download color="neutral" variant="soft" icon="i-lucide-download" class="hide-phone">
        Export CSV
      </UButton>
    </Slate>

    <div class="filters">
      <USelectMenu v-model="action" :items="actions" value-key="value" :search-input="false" icon="i-lucide-list-filter" class="w-56" aria-label="Show by action" />
      <USelectMenu v-model="actor" :items="personItems" value-key="value" :search-input="{ placeholder: 'Find a person' }" icon="i-lucide-user-round" class="w-60" aria-label="Person" />
      <UInput v-model="target" type="search" icon="i-lucide-search" placeholder="Claim number or line" class="w-64" aria-label="Claim or line" />
    </div>

    <UAlert
      v-if="chain && !chain.ok" color="error" variant="soft" icon="i-lucide-triangle-alert" role="alert" class="broken"
      :title="`The record doesn't add up from entry ${chain.firstBrokenSeq}: ${chain.reason}. Tell your privacy officer.`"
    />
    <StateNote v-if="error" kind="error" class="m-4 sm:mx-8" title="We couldn't load the activity." :body="error" retry @retry="load()" />

    <section v-for="(g, gi) in groups" :key="g.day" class="day" :aria-labelledby="`day-${gi}`">
      <h2 :id="`day-${gi}`">
        {{ g.day }}
      </h2>
      <UTimeline
        :items="g.items" color="neutral" size="md" class="log"
        :ui="{ indicator: 'bg-person-wash text-person font-bold', separator: 'bg-rule', wrapper: 'pb-4 flex items-baseline gap-4', date: 'num text-[13px] font-semibold text-muted shrink-0 w-[68px]', title: 'text-[15px] font-normal text-ink' }"
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
    <StateNote v-else-if="!entries.length && !error" class="m-4 sm:mx-8" title="Nothing matches." body="Try another person or action." />

    <div v-if="entries.length < total" class="more">
      <UButton color="neutral" variant="soft" icon="i-lucide-chevron-down" :loading="loading" @click="load(true)">
        Show older entries
      </UButton>
      <span class="text-muted text-sm num">{{ entries.length }} of {{ total }}</span>
    </div>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.broken { margin: 12px 32px 0; width: auto; }
.day { padding: 18px 32px 6px; border-bottom: 1px solid var(--cv-rule); }
.day h2 { font-size: 21px; font-weight: 700; margin-bottom: 12px; }
.log { max-width: 980px; }
.log b { font-weight: 700; }
.more { display: flex; gap: 14px; align-items: center; padding: 18px 32px 28px; }
@media (max-width: 720px) {
  .filters { padding: 12px 16px; }
  .filters > * { width: 100%; }
  .broken { margin: 10px 16px 0; }
  .day { padding: 14px 16px 4px; }
  .more { padding: 14px 16px 24px; }
}
</style>
