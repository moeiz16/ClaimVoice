<script setup lang="ts">
// The board (DESIGN.md §0.2): a screener's board of numbered lines in NEXT order. The slate (counts as words, the
// region filter), the surge band, the NEXT key, then one ruled row per caller: urgent safety first, then whoever has
// waited longest for a person, then the lines ClaimVoice is handling. "Finished this morning" closes the page as a
// table. Live through the org event stream.
import type { TableColumn } from '@nuxt/ui'
import type { ClaimSummary } from '~/types/api'
import type { BoardRow } from '~/utils/board'
import { boardRows, nextCaller } from '~/utils/board'
import { firstName, fmtDayLong, fmtTime, initials, joinWords, zoneLabel } from '~/utils/format'

useHead({ title: 'Lines · ClaimVoice' })
const { snapshot, status, error, reload } = useSwitchboard()
const { me, can } = useSession()
const listening = useListening()
const prefs = usePrefs()
const clock = useDemoClock()
const region = ref<string>('all')
const regions = [{ value: 'all', label: 'All' }, { value: 'CA-AB', label: 'Alberta' }, { value: 'US-CO', label: 'Colorado' }, { value: 'CA-QC', label: 'Québec' }]

const all = computed(() => (snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []))
// Hand-offs without a live line row stay on every view: a waiting caller is never filtered out of sight.
const rows = computed(() => all.value.filter(r => region.value === 'all' || !r.line || r.line.region === region.value))
const next = computed(() => nextCaller(all.value))
const waitingCount = computed(() => all.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting').length)
const caption = computed(() => {
  const org = me.value?.activeOrg?.name ?? 'Larkspur Mutual'
  const n = snapshot.value?.lines.length ?? 0
  return `${org} · ${fmtDayLong(clock.now.value)} · ${fmtTime(clock.now.value)} ${zoneLabel('CA-AB')} · ${n} on the line, ${waitingCount.value} waiting for a person`
})
const queueWords = computed(() => {
  if (all.value.length <= 6) return null
  const longest = Math.max(0, ...all.value.filter(r => r.handoff).map(r => clock.since(r.since)))
  return `${snapshot.value?.lines.length ?? 0} on the line, ${waitingCount.value} waiting, longest wait ${Math.max(1, Math.round(longest / 60))} min`
})
const lastEnded = computed(() => {
  const c = snapshot.value?.recentClaims[0]
  return c ? fmtTime(c.reportedAt) : null
})

async function takeNext() {
  if (next.value) await takeRow(next.value)
}
async function takeRow(r: BoardRow) {
  const l = listening.fromLine({ callId: r.callId, lineLabel: r.lineLabel, callerLabel: r.callerLabel, place: r.place, language: r.language, answeredAt: r.since })
  if (await listening.acceptHandoff(l)) await navigateTo(`/lines/${r.callId}`)
}

// Read the summary: a slide-over from the left, so the board stays in view.
const summaryOf = ref<BoardRow | null>(null)
const summaryOpen = computed({ get: () => !!summaryOf.value, set: (v: boolean) => { if (!v) summaryOf.value = null } })

const placeOf = (c: ClaimSummary) => (c.lossPlace ?? c.regionLabel).split(',').pop()!.trim()
const finishedCols: TableColumn<ClaimSummary>[] = [
  { accessorKey: 'claimNumber', header: 'Claim' },
  { accessorKey: 'holderName', header: 'Caller' },
  { id: 'place', header: 'Where', cell: ({ row }) => placeOf(row.original) },
  { id: 'loss', header: 'What happened', cell: ({ row }) => row.original.lossTypeLabel },
  { id: 'time', header: 'Reported', cell: ({ row }) => fmtTime(row.original.reportedAt) },
  { id: 'route', header: 'Where it went' },
]
function openClaim(row: { original: ClaimSummary }) { void navigateTo(`/claims/${row.original.id}`) }
</script>

<template>
  <div>
    <Slate title="Lines" :caption="caption">
      <UTabs v-model="region" :items="regions" :content="false" variant="pill" size="sm" color="neutral" class="hide-phone" aria-label="Show lines in" />
      <UButton color="neutral" variant="soft" :icon="prefs.theme.value === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'" class="hide-phone" :aria-label="prefs.theme.value === 'dark' ? 'Switch to day line' : 'Switch to night line'" @click="prefs.toggleTheme()" />
    </Slate>

    <StateNote v-if="status === 'lost' || status === 'error'" kind="error" class="m-4 sm:mx-8" title="We lost the connection to the lines." body="Calls carry on; ClaimVoice keeps taking them. Reconnecting…" retry @retry="reload" />
    <SurgeBand v-if="snapshot?.surge" :surge="snapshot.surge" :queue-words="queueWords" @updated="s => snapshot && (snapshot.surge = s)" />

    <div class="nextbar">
      <UButton v-if="can('calls:handoff')" size="xl" icon="i-lucide-phone-incoming" :color="next?.lamp === 'urgent' ? 'primary' : 'neutral'" :disabled="!next" @click="takeNext">
        Take the next caller
      </UButton>
      <p v-if="next" class="nextwho">
        <b>{{ next.callerLabel }}</b> · {{ next.lineLabel }} · {{ next.stateWord.toLowerCase() }}, waiting <time class="num">{{ clock.elapsed(next.since) }}</time>
      </p>
      <p v-else class="nextwho">
        <UIcon name="i-lucide-check" class="size-4 text-fast" />Nobody is waiting for a person. ClaimVoice has every line.
      </p>
      <span class="order"><UKbd value="N" class="hide-phone" />Urgent first, then the longest wait, then the lines</span>
    </div>

    <div v-if="!snapshot && !error" aria-busy="true" aria-label="Loading the lines" class="loading">
      <div v-for="n in 4" :key="n" class="skel">
        <USkeleton class="h-14 w-14 rounded-lg" /><USkeleton class="h-6 w-40" /><USkeleton class="h-6 flex-1" /><USkeleton class="h-10 w-56" />
      </div>
    </div>

    <template v-else-if="snapshot">
      <ol v-if="rows.length" class="board" aria-label="Callers, in the order to take them">
        <BoardLine v-for="r in rows" :key="r.id" :row="r" @summary="x => summaryOf = x" />
      </ol>
      <div v-else class="quiet">
        <div class="flat" aria-hidden="true" />
        <p>All quiet on the lines.<span v-if="lastEnded"> The last call ended at {{ lastEnded }}.</span></p>
      </div>

      <div v-if="snapshot.freePeople.length" class="free">
        <UAvatarGroup size="sm" :max="4">
          <UTooltip v-for="p in snapshot.freePeople" :key="p.id" :text="p.name">
            <UAvatar :text="initials(p.name)" class="bg-person-wash text-person font-bold" />
          </UTooltip>
        </UAvatarGroup>
        <span>{{ joinWords(snapshot.freePeople.map(p => firstName(p.name))) }} {{ snapshot.freePeople.length === 1 ? 'is' : 'are' }} free to take calls</span>
      </div>

      <section v-if="snapshot.recentClaims.length" class="finished" aria-labelledby="fin-h">
        <h2 id="fin-h">
          Finished this morning <NuxtLink to="/claims">All claims</NuxtLink>
        </h2>
        <UTable :data="snapshot.recentClaims" :columns="finishedCols" class="tbl" :ui="{ tr: 'cursor-pointer hover:bg-sunk' }" @select="openClaim">
          <template #claimNumber-cell="{ row }">
            <NuxtLink :to="`/claims/${row.original.id}`" class="font-semibold num">{{ row.original.claimNumber }}</NuxtLink>
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

    <USlideover v-model:open="summaryOpen" side="left" :title="summaryOf ? `${summaryOf.callerLabel} · ${summaryOf.lineLabel}` : 'Summary'" :description="summaryOf?.stateWord">
      <template #body>
        <div v-if="summaryOf?.handoff" class="grid gap-4 text-[15px]">
          <p class="voice text-lg">{{ summaryOf.handoff.detail }}</p>
          <p>{{ summaryOf.handoff.summary }}</p>
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
            Back to the board
          </UButton>
        </div>
      </template>
    </USlideover>
  </div>
</template>

<style scoped>
.nextbar { display: flex; align-items: center; gap: 10px 18px; flex-wrap: wrap; padding: 16px 32px; border-bottom: 1px solid var(--cv-rule); }
.nextwho { margin: 0; display: flex; align-items: center; gap: 6px; font-size: 15px; }
.nextwho b { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 680; font-size: 17px; }
.order { margin-left: auto; display: inline-flex; gap: 8px; align-items: center; color: var(--cv-muted); font-size: 13px; }
.board { margin: 0; padding: 0; }
.loading { display: grid; }
.skel { display: flex; align-items: center; gap: 20px; padding: 16px 32px; border-bottom: 1px solid var(--cv-rule); }
.quiet { padding: 72px 32px; display: grid; place-items: center; gap: 18px; border-bottom: 1px solid var(--cv-rule); }
.quiet .flat { width: 80%; height: 2px; border-radius: 2px; background: var(--cv-faint); animation: breathe var(--m-breathe) var(--ease-breath) infinite; }
.quiet p { font-family: var(--font-voice); font-size: 22px; font-weight: 600; color: var(--cv-muted); margin: 0; }
.free { display: flex; align-items: center; gap: 10px; padding: 14px 32px; color: var(--cv-muted); font-size: 14px; border-bottom: 1px solid var(--cv-rule); }
.finished { padding: 22px 32px 0; }
.finished h2 { font-size: 19px; font-weight: 650; display: flex; gap: 12px; align-items: baseline; margin-bottom: 8px; }
.finished h2 a { font-family: var(--font-sans); font-size: 14px; font-weight: 600; }
.tbl { border-top: 1px solid var(--cv-rule); }
@media (max-width: 720px) {
  .nextbar, .free, .finished { padding-left: 16px; padding-right: 16px; }
  .order { display: none; }
  .nextwho { display: block; }
  .tbl { overflow-x: auto; }
}
</style>
