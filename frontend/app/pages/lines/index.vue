<script setup lang="ts">
// Lines (DESIGN.md §3): "Who's on the line?" answered in one sentence, the weather note, then the callers in pools
// by who they need: waiting for a person (urgent first, then the longest wait), talking with ClaimVoice (by line),
// with a person. Finished this morning closes the page as pebble rows. Live through the org event stream.
import type { TableColumn } from '@nuxt/ui'
import type { ClaimSummary } from '~/types/api'
import type { BoardRow } from '~/utils/board'
import { boardRows } from '~/utils/board'
import { firstName, fmtDayLong, fmtTime, initials, joinWords, zoneLabel } from '~/utils/format'
import { questionFor } from '~/utils/places'

useHead({ title: 'Lines · ClaimVoice' })
const { snapshot, status, error, reload } = useSwitchboard()
const { me, can } = useSession()
const listening = useListening()
const clock = useDemoClock()
const region = ref<string>('all')
const regions = [{ value: 'all', label: 'Everywhere' }, { value: 'CA-AB', label: 'Alberta' }, { value: 'US-CO', label: 'Colorado' }, { value: 'CA-QC', label: 'Québec' }]

const all = computed(() => (snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []))
// Hand-offs without a live line stay on every view: a waiting caller is never filtered out of sight.
const rows = computed(() => all.value.filter(r => region.value === 'all' || !r.line || r.line.region === region.value))
const waitingRows = computed(() => rows.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting'))
const lineRows = computed(() => rows.value.filter(r => r.lamp === 'line' || r.lamp === 'ringing'))
const personRows = computed(() => rows.value.filter(r => r.lamp === 'person'))
const waitingAll = computed(() => all.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting'))

const eyebrow = computed(() => `${me.value?.activeOrg?.name ?? 'Larkspur Mutual'} · ${fmtDayLong(clock.now.value)} · ${fmtTime(clock.now.value)} ${zoneLabel('CA-AB')}`)
const answer = computed(() => {
  if (!snapshot.value) return ''
  const withCv = all.value.filter(r => r.lamp === 'line').length
  const w = waitingAll.value
  const first = w[0]
  const cv = `${withCv} call${withCv === 1 ? '' : 's'} with ClaimVoice`
  if (!w.length) return `${cv}, and nobody is waiting for a person.`
  return `${cv}. ${w.length} caller${w.length > 1 ? 's are' : ' is'} waiting for a person; ${firstName(first!.callerLabel)} first, ${first!.lamp === 'urgent' ? 'for urgent safety' : 'waiting'} ${clock.elapsed(first!.since)}.`
})
const queueWords = computed(() => {
  if (all.value.length <= 6) return null
  const longest = Math.max(0, ...all.value.filter(r => r.handoff).map(r => clock.since(r.since)))
  return `${snapshot.value?.lines.length ?? 0} on the line, ${waitingAll.value.length} waiting, longest wait ${Math.max(1, Math.round(longest / 60))} min`
})
const lastEnded = computed(() => {
  const c = snapshot.value?.recentClaims[0]
  return c ? fmtTime(c.reportedAt) : null
})

async function takeRow(r: BoardRow) {
  const l = listening.fromLine({ callId: r.callId, lineLabel: r.lineLabel, callerLabel: r.callerLabel, place: r.place, language: r.language, answeredAt: r.since })
  if (await listening.acceptHandoff(l)) await navigateTo(`/lines/${r.callId}`)
}

// Read the summary: a slide-over, so the pools stay in view.
const summaryOf = ref<BoardRow | null>(null)
const summaryOpen = computed({ get: () => !!summaryOf.value, set: (v: boolean) => { if (!v) summaryOf.value = null } })

const placeOf = (c: ClaimSummary) => (c.lossPlace ?? c.regionLabel).split(',').pop()!.trim()
const finishedCols: TableColumn<ClaimSummary>[] = [
  { accessorKey: 'holderName', header: 'Caller' },
  { accessorKey: 'claimNumber', header: 'Claim' },
  { id: 'loss', header: 'What happened', cell: ({ row }) => row.original.lossTypeLabel },
  { id: 'place', header: 'Where', cell: ({ row }) => placeOf(row.original) },
  { id: 'time', header: 'Reported', cell: ({ row }) => fmtTime(row.original.reportedAt) },
  { id: 'route', header: 'Where it went' },
]
function openClaim(row: { original: ClaimSummary }) { void navigateTo(`/claims/${row.original.id}`) }
</script>

<template>
  <div>
    <PageHead :title="questionFor('lines')" :eyebrow="eyebrow" :caption="answer">
      <UTabs v-model="region" :items="regions" :content="false" size="sm" color="neutral" class="hide-phone" aria-label="Show lines in" />
    </PageHead>

    <StateNote v-if="status === 'lost' || status === 'error'" kind="error" class="mb-5" title="We lost the connection to the lines." body="Calls carry on; ClaimVoice keeps taking them. Reconnecting…" retry @retry="reload" />
    <WeatherNote v-if="snapshot?.surge" :surge="snapshot.surge" :queue-words="queueWords" class="mb-8" @updated="s => snapshot && (snapshot.surge = s)" />

    <div v-if="!snapshot && !error" aria-busy="true" aria-label="Loading the lines" class="loading">
      <USkeleton v-for="n in 3" :key="n" class="h-56 rounded-[28px]" />
    </div>

    <template v-else-if="snapshot">
      <section v-if="waitingRows.length" class="pool" aria-labelledby="p-wait">
        <h2 id="p-wait" class="pool-h">
          Waiting for a person <span class="n num">{{ waitingRows.length }}</span>
        </h2>
        <p class="pool-sub">
          Urgent safety first, then whoever has waited longest. Take the call, or read what ClaimVoice handed over.
        </p>
        <ol class="grid wait">
          <CallCard v-for="(r, i) in waitingRows" :key="r.id" :row="r" :index="i" @summary="x => summaryOf = x" />
        </ol>
      </section>

      <section v-if="lineRows.length" class="pool" aria-labelledby="p-cv">
        <h2 id="p-cv" class="pool-h">
          Talking with ClaimVoice <span class="n num">{{ lineRows.length }}</span>
        </h2>
        <p class="pool-sub">
          The question ClaimVoice asked last, and what it has heard so far. Listen in, whisper a note, or take over.
        </p>
        <ol class="grid cv">
          <CallCard v-for="(r, i) in lineRows" :key="r.id" :row="r" :index="i" />
        </ol>
      </section>

      <section v-if="personRows.length" class="pool" aria-labelledby="p-person">
        <h2 id="p-person" class="pool-h">
          With a person <span class="n num">{{ personRows.length }}</span>
        </h2>
        <ol class="grid cv">
          <CallCard v-for="(r, i) in personRows" :key="r.id" :row="r" :index="i" />
        </ol>
      </section>

      <div v-if="!rows.length" class="quiet">
        <CvMark :size="72" />
        <p class="round">
          All quiet on the lines.<span v-if="lastEnded"> The last call ended at {{ lastEnded }}.</span>
        </p>
      </div>

      <p v-if="snapshot.freePeople.length" class="free">
        <span class="faces" aria-hidden="true">
          <span v-for="p in snapshot.freePeople.slice(0, 4)" :key="p.id" class="face">{{ initials(p.name) }}</span>
        </span>
        {{ joinWords(snapshot.freePeople.map(p => firstName(p.name))) }} {{ snapshot.freePeople.length === 1 ? 'is' : 'are' }} free to take calls.
      </p>

      <section v-if="snapshot.recentClaims.length" class="pool" aria-labelledby="fin-h">
        <h2 id="fin-h" class="pool-h">
          Finished this morning <span class="n num">{{ snapshot.recentClaims.length }}</span>
          <UButton to="/claims" color="primary" variant="link" trailing-icon="i-lucide-arrow-right" size="md" class="ml-auto">
            Which claims came in?
          </UButton>
        </h2>
        <UTable :data="snapshot.recentClaims" :columns="finishedCols" class="tbl" :ui="{ tr: 'cursor-pointer' }" @select="openClaim">
          <template #holderName-cell="{ row }">
            <span class="hn">
              <span class="face sm" aria-hidden="true">{{ initials(row.original.holderName) }}</span>
              <NuxtLink :to="`/claims/${row.original.id}`" class="font-medium text-ink no-underline">{{ row.original.holderName }}</NuxtLink>
            </span>
          </template>
          <template #claimNumber-cell="{ row }">
            <span class="num text-muted">{{ row.original.claimNumber }}</span>
          </template>
          <template #route-cell="{ row }">
            <span class="flex gap-1.5 flex-wrap">
              <RouteTag v-if="row.original.route" :route="row.original.route.route" :label="row.original.route.label" />
              <RouteTag v-if="row.original.siuOpen && row.original.route?.route !== 'special_investigation'" route="special_investigation" />
              <span v-if="!row.original.route" class="text-muted text-sm">{{ row.original.statusLabel }}</span>
            </span>
          </template>
        </UTable>
      </section>
    </template>

    <USlideover v-model:open="summaryOpen" side="right" :title="summaryOf ? `What ${firstName(summaryOf.callerLabel)} needs` : 'Summary'" :description="summaryOf ? `${summaryOf.lineLabel} · ${summaryOf.stateWord}` : undefined">
      <template #body>
        <div v-if="summaryOf?.handoff" class="grid gap-4 text-[15px]">
          <p class="sumq round">
            {{ summaryOf.handoff.detail }}
          </p>
          <p class="whitespace-pre-line">
            {{ summaryOf.handoff.summary }}
          </p>
          <p v-if="summaryOf.handoff.actionsTaken.length" class="text-muted text-sm">
            ClaimVoice {{ summaryOf.handoff.actionsTaken.map(a => a.charAt(0).toLowerCase() + a.slice(1)).join('; ') }}.
          </p>
        </div>
      </template>
      <template #footer>
        <div v-if="summaryOf" class="flex gap-2">
          <UButton v-if="can('calls:handoff')" icon="i-lucide-phone" @click="takeRow(summaryOf)">
            Take the call
          </UButton>
          <UButton color="neutral" variant="soft" @click="summaryOf = null">
            Not yet
          </UButton>
        </div>
      </template>
    </USlideover>
  </div>
</template>

<style scoped>
.pool { margin-top: 36px; }
.pool:first-of-type { margin-top: 8px; }
.pool-sub { margin: 6px 0 16px; color: var(--cv-muted); font-size: 14.5px; }
.grid { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px; }
.grid.wait { grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr)); }
.grid.cv { grid-template-columns: repeat(auto-fill, minmax(min(100%, 360px), 1fr)); }
.pool-h + .tbl, .pool-h ~ .tbl { margin-top: 10px; }
.loading { display: grid; gap: 16px; }
.quiet { padding: 64px 16px; display: grid; place-items: center; gap: 16px; text-align: center; }
.quiet p { font-size: 26px; font-weight: 900; color: var(--cv-muted); margin: 0; }
.free { margin: 28px 0 0; display: flex; align-items: center; gap: 12px; color: var(--cv-muted); font-size: 14.5px; }
.faces { display: inline-flex; }
.face { width: 36px; height: 36px; border-radius: 50%; display: inline-grid; place-items: center; background: var(--cv-person-wash); color: var(--cv-person); font-family: var(--font-round); font-weight: 900; font-size: 13px; box-shadow: 0 0 0 3px var(--cv-bg); }
.face + .face { margin-left: -8px; }
.face.sm { width: 32px; height: 32px; font-size: 12px; background: var(--cv-sand); color: var(--cv-caller); box-shadow: none; }
.hn { display: inline-flex; align-items: center; gap: 10px; }
.sumq { font-size: 22px; line-height: 1.25; font-weight: 850; padding: 14px 18px; border-radius: 6px 22px 22px 22px; background: var(--cv-sand); }
@media (max-width: 720px) {
  .pool { margin-top: 28px; }
}
</style>
