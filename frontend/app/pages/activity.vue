<script setup lang="ts">
// Activity: the audit trail as day-grouped sentences with initials, filter pills by person, action and claim, and a
// "Record intact" check of the hash chain. Export as CSV.
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
const people = ref<Member[]>([])
const actor = ref('')
const action = ref('')
const target = ref('')
const targetD = refDebounced(target, 300)
const loading = ref(true)
const error = ref<string | null>(null)
const actions = [
  { key: '', label: 'Everything' }, { key: 'call.', label: 'Calls' }, { key: 'claim.', label: 'Claims and routes' },
  { key: 'check.', label: 'Routing checks' }, { key: 'qa.', label: 'Quality' }, { key: 'settings.', label: 'Settings' },
  { key: 'surge.', label: 'Surge' }, { key: 'auth.', label: 'Sign-ins' },
]
const query = computed(() => ({ action: action.value || undefined, actor: actor.value || undefined, target: targetD.value || undefined }))

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
onMounted(async () => {
  void api.audit.verify().then((c) => { chain.value = c }).catch(() => null)
  people.value = await api.org.members().catch(() => [])
})
watch(query, () => load(), { immediate: true })

const groups = computed(() => {
  const out: { day: string, items: AuditEntry[] }[] = []
  for (const e of entries.value) {
    const day = fmtDayGroup(e.at, clock.now.value)
    const g = out[out.length - 1]
    if (g && g.day === day) g.items.push(e)
    else out.push({ day, items: [e] })
  }
  return out
})
/** "Renée Kowalchuk took over Line 1 …": bold the actor and the action words. */
function parts(e: AuditEntry): { lead: string, rest: string } {
  const lead = `${e.actorLabel} ${e.actionLabel}`
  if (e.summary.startsWith(lead)) return { lead, rest: e.summary.slice(lead.length) }
  if (e.summary.startsWith(e.actorLabel)) return { lead: e.actorLabel, rest: e.summary.slice(e.actorLabel.length) }
  return { lead: '', rest: e.summary }
}
const exportUrl = computed(() => api.audit.exportUrl(query.value))
</script>

<template>
  <div>
    <PageHeader title="Activity" :caption="`Every sensitive action at Larkspur Mutual, newest first${total ? ` · ${total} entries` : ''}`">
      <span v-if="chain" class="tag hide-phone" :class="chain.ok ? 'fast' : 'urgent'" :title="`${chain.checked} entries checked`">
        <CvIcon :name="chain.ok ? 'check' : 'urgent'" size="s" />{{ chain.ok ? `Record intact · checked ${fmtTime(chain.checkedAt)}` : `Record broken at entry ${chain.firstBrokenSeq}` }}
      </span>
      <a class="btn soft sm hide-phone" :href="exportUrl" download><CvIcon name="download" size="s" />Export CSV</a>
    </PageHeader>
    <div class="filters">
      <div class="pills" role="group" aria-label="Show by action">
        <button v-for="a in actions" :key="a.key" type="button" class="pill" :aria-pressed="action === a.key" @click="action = a.key">
          {{ a.label }}
        </button>
      </div>
      <select v-model="actor" class="field-input sm sel" aria-label="Person">
        <option value="">
          Everyone
        </option>
        <option v-for="p in people" :key="p.userId" :value="p.userId">
          {{ p.fullName }}
        </option>
      </select>
      <label class="search"><CvIcon name="search" size="s" /><span class="sr-only-cv">Claim or line</span><input v-model="target" type="search" placeholder="Claim number or line"></label>
    </div>
    <p v-if="chain && !chain.ok" class="broken" role="alert">
      <CvIcon name="urgent" size="s" />The record doesn't add up from entry {{ chain.firstBrokenSeq }}: {{ chain.reason }}. Tell your privacy officer.
    </p>
    <StateNote v-if="error" kind="error" title="We couldn't load the activity." :body="error" retry class="wrap" @retry="load()" />
    <section v-for="g in groups" :key="g.day" class="day wrap" :aria-label="g.day">
      <h2>{{ g.day }}</h2>
      <ol>
        <li v-for="e in g.items" :key="e.id">
          <span class="avatar sm">{{ initials(e.actorLabel) }}</span>
          <p><b v-if="parts(e).lead">{{ parts(e).lead }}</b>{{ parts(e).rest }}</p>
          <time class="num">{{ fmtTime(e.at) }}</time>
        </li>
      </ol>
    </section>
    <div v-if="loading && !entries.length" class="wrap">
      <span v-for="n in 6" :key="n" class="skeleton" style="display:block; height: 44px; margin-bottom: 8px; border-radius: 14px" />
    </div>
    <StateNote v-else-if="!entries.length && !error" class="wrap" title="Nothing matches." body="Try another person or action." />
    <div v-if="entries.length < total" class="more">
      <button class="btn soft" type="button" :disabled="loading" @click="load(true)">
        Show older entries
      </button>
    </div>
  </div>
</template>

<style scoped>
.wrap { margin-left: 32px; margin-right: 32px; }
.filters { display: flex; gap: 10px; align-items: center; margin: 0 32px 6px; flex-wrap: wrap; }
.pills { display: flex; gap: 6px; flex-wrap: wrap; }
.pill { height: 36px; padding: 0 14px; border-radius: 999px; border: 0; background: var(--cv-sunk); font-weight: 650; font-size: 13.5px; color: var(--cv-muted); }
.pill[aria-pressed="true"] { background: var(--cv-ink); color: var(--cv-bg); }
.sel { width: auto; min-width: 180px; margin-left: auto; }
.search { display: flex; align-items: center; gap: 8px; height: 42px; padding: 0 16px; border-radius: 999px; background: var(--cv-surface); box-shadow: inset 0 0 0 1.5px var(--cv-sunk-2); color: var(--cv-muted); }
.search input { border: 0; background: transparent; font: inherit; font-size: 14px; color: var(--cv-ink); width: 180px; }
.search input:focus { outline: none; }
.broken { margin: 6px 32px; color: var(--cv-urgent); font-weight: 650; display: flex; gap: 6px; align-items: center; }
.day { margin-top: 18px; }
.day h2 { font-size: 21px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 8px; }
ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
li { display: grid; grid-template-columns: 36px 1fr auto; gap: 12px; align-items: center; background: var(--cv-surface); border-radius: 14px; padding: 8px 14px 8px 8px; }
.avatar.sm { width: 32px; height: 32px; font-size: 11.5px; }
li p { margin: 0; font-size: 15px; }
li b { font-weight: 700; }
li time { color: var(--cv-muted); font-size: 13px; font-weight: 650; }
.more { display: flex; justify-content: center; margin-top: 18px; }
@media (max-width: 720px) {
  .wrap, .filters { margin-left: 16px; margin-right: 16px; }
  .sel { margin-left: 0; }
  .search input { width: 140px; }
  li { grid-template-columns: 32px 1fr; }
  li time { grid-column: 2; }
}
</style>
