<script setup lang="ts">
// The line desk (DESIGN.md §5.3): surge ribbon, one channel strip per live call, the hand-off tray, finished-claim
// tickets. Counts are words in the caption, not KPI tiles. Live through the org event stream.
import { LayoutGroup } from 'motion-v'
import { fmtDayLong, fmtTime, zoneLabel } from '~/utils/format'

useHead({ title: 'Lines · ClaimVoice' })
const { snapshot, status, error, reload } = useSwitchboard()
const { me } = useSession()
const prefs = usePrefs()
const clock = useDemoClock()
const region = ref<'all' | 'CA-AB' | 'US-CO' | 'CA-QC'>('all')
const regions = [{ key: 'all', label: 'All' }, { key: 'CA-AB', label: 'Alberta' }, { key: 'US-CO', label: 'Colorado' }, { key: 'CA-QC', label: 'Québec' }] as const

const lines = computed(() => (snapshot.value?.lines ?? []).filter(l => region.value === 'all' || l.region === region.value))
const tray = computed(() => (snapshot.value?.handoffTray ?? []).filter(h => h.state === 'waiting'))
const density = computed(() => (lines.value.length > 12 ? 'rows' : lines.value.length > 6 ? 'compact' : 'normal'))
const caption = computed(() => {
  const org = me.value?.activeOrg?.name ?? 'Larkspur Mutual'
  const n = snapshot.value?.lines.length ?? 0
  const w = tray.value.length
  return `${org} · ${fmtDayLong(clock.now.value)} · ${fmtTime(clock.now.value)} ${zoneLabel('CA-AB')} · ${n} on the line, ${w} waiting for a person`
})
const queueWords = computed(() => {
  if (density.value === 'normal') return null
  const longest = Math.max(0, ...tray.value.map(h => clock.since(h.requestedAt)))
  return `${lines.value.length} on the line, ${tray.value.length} waiting, longest wait ${Math.max(1, Math.round(longest / 60))} min`
})
const lastEnded = computed(() => {
  const c = snapshot.value?.recentClaims[0]
  return c ? fmtTime(c.reportedAt) : null
})
</script>

<template>
  <div>
    <PageHeader title="Lines" :caption="caption">
      <div class="seg hide-phone" role="group" aria-label="Show lines">
        <button v-for="r in regions" :key="r.key" type="button" :aria-pressed="region === r.key" @click="region = r.key">
          {{ r.label }}
        </button>
      </div>
      <button class="iconbtn hide-phone" type="button" :aria-label="prefs.theme.value === 'dark' ? 'Switch to day line' : 'Switch to night line'" @click="prefs.toggleTheme()">
        <CvIcon :name="prefs.theme.value === 'dark' ? 'sun' : 'moon'" />
      </button>
    </PageHeader>

    <div class="pad">
      <StateNote v-if="status === 'lost' || status === 'error'" kind="error" title="We lost the connection to the lines." body="Calls carry on; ClaimVoice keeps taking them. Reconnecting…" retry class="mb" @retry="reload" />
      <SurgeRibbon v-if="snapshot?.surge" :surge="snapshot.surge" :queue-words="queueWords" @updated="s => snapshot && (snapshot.surge = s)" />
    </div>

    <div v-if="!snapshot && !error" class="desk" aria-busy="true" aria-label="Loading the lines">
      <div v-for="n in 3" :key="n" class="strip-skel">
        <span class="skeleton" style="width: 40%; height: 26px" />
        <span class="skeleton" style="width: 70%; height: 30px" />
        <div class="bars">
          <i v-for="b in 24" :key="b" :style="{ animationDelay: `${(b + n * 3) * 60}ms`, height: `${20 + ((b * 37 + n * 11) % 60)}%` }" />
        </div>
        <span class="skeleton" style="height: 64px; border-radius: 20px" />
        <span class="skeleton" style="width: 85%; height: 30px" />
      </div>
      <div class="tray-skel skeleton" />
    </div>

    <LayoutGroup v-else-if="snapshot">
      <div class="desk" :class="density">
        <template v-if="lines.length">
          <LineStrip v-for="l in lines" :key="l.callId" :line="l" :compact="density !== 'normal'" />
        </template>
        <div v-else class="quiet">
          <div class="flat" aria-hidden="true" />
          <p>All quiet on the lines.<span v-if="lastEnded"> The last call ended at {{ lastEnded }}.</span></p>
        </div>
        <HandoffTray :items="tray" :free="snapshot.freePeople" class="tray-cell" />
      </div>
    </LayoutGroup>

    <FinishedTickets v-if="snapshot?.recentClaims.length" :claims="snapshot.recentClaims" />
  </div>
</template>

<style scoped>
.pad { margin: 0 32px; display: grid; gap: 10px; }
.desk { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) 372px; gap: 14px; margin: 14px 32px 0; align-items: start; }
.desk.compact { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
.desk.compact .tray-cell { grid-column: 1 / -1; grid-row: 1; }
.desk.rows { grid-template-columns: 1fr 1fr; }
.desk.rows .tray-cell { grid-column: 1 / -1; grid-row: 1; }
.tray-cell { grid-column: 4; grid-row: 1 / span 3; }
.quiet { grid-column: 1 / span 3; background: var(--cv-surface); border-radius: 28px; padding: 64px 28px; display: grid; place-items: center; gap: 18px; }
.quiet .flat { width: 80%; height: 2px; border-radius: 2px; background: var(--cv-faint); animation: breathe var(--m-breathe) var(--ease-breath) infinite; }
.quiet p { font-family: var(--font-display); font-size: 22px; font-weight: 600; color: var(--cv-muted); margin: 0; }
.strip-skel { background: var(--cv-surface); border-radius: 28px; padding: 18px 18px 18px 28px; display: grid; gap: 12px; }
.strip-skel .bars { display: flex; align-items: center; gap: 3px; height: 44px; }
.strip-skel .bars i { flex: 1; border-radius: 2px; background: var(--cv-sunk-2); animation: bar-pulse 1.2s var(--ease-breath) infinite; }
.tray-skel { height: 420px; border-radius: 28px; }
.mb { margin-bottom: 4px; }
@media (max-width: 1280px) {
  .desk { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tray-cell { grid-column: 1 / -1; grid-row: 1; }
}
@media (max-width: 720px) {
  .pad { margin: 0 16px; }
  .desk, .desk.compact, .desk.rows { grid-template-columns: 1fr; margin: 12px 16px 0; }
  .quiet { grid-column: 1; }
}
</style>
