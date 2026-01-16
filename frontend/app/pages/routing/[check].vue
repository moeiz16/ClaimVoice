<script setup lang="ts">
// A routing check's fact sheet, read as a document of answers (DESIGN.md §3): each section a rounded card with its
// number in a pebble (what it's for and not for, what it looks at in words, how it was tested, known limits), then
// the fairness results and the sign-off history, with the technical measures folded away for the reviewer.
import type { TableColumn, TimelineItem } from '@nuxt/ui'
import type { FactSheet, Fairness, FairnessRow, MetricSet } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDate, fmtDayShort, pct } from '~/utils/format'

const route = useRoute()
const key = computed(() => String(route.params.check))
const sheet = ref<FactSheet | null>(null)
const fairness = ref<Fairness | null>(null)
const error = ref<string | null>(null)
useHead(() => ({ title: `${sheet.value?.name ?? 'Fact sheet'} · ClaimVoice` }))

async function load() {
  error.value = null
  sheet.value = null
  try {
    const [s, f] = await Promise.all([api.routing.factSheet(key.value), api.routing.fairness(key.value).catch(() => null)])
    sheet.value = s
    fairness.value = f
  }
  catch (e) { error.value = (e as Error).message }
}
watch(key, load, { immediate: true })

// Which check: tabs that move between the two fact sheets.
const checks = [{ value: 'size', label: 'Size check' }, { value: 'closer_look', label: 'Closer-look check' }]
const which = computed({ get: () => key.value, set: (k: string | number) => { if (k !== key.value) void navigateTo(`/routing/${k}`) } })

const main = computed(() => (sheet.value?.sections ?? []).filter(s => s.key !== 'technical'))
const fold = computed(() => sheet.value?.sections.find(s => s.key === 'technical') ?? null)
const tech = computed(() => sheet.value?.technical ?? null)
const nFair = computed(() => main.value.length + 1)
const nVersions = computed(() => main.value.length + (fairness.value ? 2 : 1))

// Fairness results: one row per group, grouped by what was compared.
const dims = { region: 'Region', language: 'Language of the call', age_band: 'Age of policyholder' } as const
const dimOrder = ['region', 'language', 'age_band'] as const
const fairRows = computed(() => dimOrder.flatMap(d => (fairness.value?.rows ?? []).filter(r => r.dimension === d)))
const firstOfDim = (i: number) => i === 0 || fairRows.value[i - 1]?.dimension !== fairRows.value[i]?.dimension
const fairCols: TableColumn<FairnessRow>[] = [
  { id: 'dimension', header: 'Compared by' },
  { accessorKey: 'label', header: 'Group' },
  { accessorKey: 'count', header: 'Claims', cell: ({ row }) => row.original.count.toLocaleString('en-CA') },
  { id: 'rate', header: 'Sent for a closer look', cell: ({ row }) => pct(row.original.flaggedRate) },
  { id: 'band', header: 'Inside the allowed band?' },
]

// Sign-off history as a timeline, newest version first.
const versionItems = computed<TimelineItem[]>(() => (sheet.value?.versions ?? []).map(v => ({
  value: v.version,
  title: `Version ${v.version}`,
  date: v.stage === 'in_use' ? `In use${v.inUseSince ? ` since ${fmtDate(v.inUseSince)}` : ''}` : v.stage === 'candidate' ? 'On trial' : 'Retired',
  description: v.trainedOn,
  icon: v.stage === 'in_use' ? 'i-lucide-check' : v.stage === 'candidate' ? 'i-lucide-clock' : 'i-lucide-archive',
  version: v,
})))

// For the technical reviewer.
interface MetricRow { name: string, m: MetricSet }
const metricRows = computed<MetricRow[]>(() => {
  const t = tech.value
  if (!t) return []
  const rows: MetricRow[] = [{ name: 'Gradient-boosted trees (in use)', m: t.test }]
  if (t.randomForest) rows.push({ name: 'Random forest (challenger)', m: t.randomForest })
  rows.push({ name: 'Logistic baseline', m: t.baseline })
  return rows
})
const two = (n: number) => n.toFixed(2)
const metricCols: TableColumn<MetricRow>[] = [
  { accessorKey: 'name', header: 'Measured on the test period' },
  { id: 'auc', header: 'Area under ROC', cell: ({ row }) => two(row.original.m.auc) },
  { id: 'prAuc', header: 'Area under precision–recall', cell: ({ row }) => two(row.original.m.prAuc) },
  { id: 'brier', header: 'Brier', cell: ({ row }) => two(row.original.m.brier) },
  { id: 'ece', header: 'Calibration error', cell: ({ row }) => two(row.original.m.ece) },
]
interface CalRow { predicted: number, observed: number, count: number }
const calCols: TableColumn<CalRow>[] = [
  { id: 'predicted', header: 'Predicted', cell: ({ row }) => pct(row.original.predicted, 0) },
  { id: 'observed', header: 'What happened', cell: ({ row }) => pct(row.original.observed, 0) },
  { accessorKey: 'count', header: 'Claims' },
]
const techItems = [{ label: 'For the technical reviewer', icon: 'i-lucide-sliders-horizontal', slot: 'tech' as const }]
</script>

<template>
  <div>
    <PageHead :title="sheet?.name ?? 'Fact sheet'" :caption="sheet ? `The fact sheet for version ${sheet.version}: what it is for, how it was tested, and who signed it off.` : ''" :back="{ to: '/routing', label: 'Routing checks' }">
      <UTabs v-model="which" :items="checks" :content="false" size="sm" color="neutral" class="hide-phone" aria-label="Which check" />
    </PageHead>

    <StateNote v-if="error" kind="error" class="mb-4" title="We couldn't load this fact sheet." :body="error" retry @retry="load" />

    <article v-if="sheet" class="doc">
      <section v-for="(s, i) in main" :key="s.key" class="sec" :aria-labelledby="`fs-${s.key}`">
        <span class="no num" aria-hidden="true">{{ i + 1 }}</span>
        <h2 :id="`fs-${s.key}`">
          {{ s.title }}
        </h2>
        <div class="body">
          <ul v-if="s.body.length > 1">
            <li v-for="(b, j) in s.body" :key="j">
              {{ b }}
            </li>
          </ul>
          <p v-else>
            {{ s.body[0] }}
          </p>
        </div>
      </section>

      <section v-if="fairness" class="sec" aria-labelledby="fs-fair">
        <span class="no num" aria-hidden="true">{{ nFair }}</span>
        <h2 id="fs-fair">
          Fairness, version {{ fairness.version }}
        </h2>
        <div class="body">
          <p>
            Overall <b class="num">{{ pct(fairness.overallRate) }}</b> are sent for a closer look; the allowed band is <b class="num">{{ (fairness.band * 100).toFixed(1) }} points</b> either side.
          </p>
          <UTable :data="fairRows" :columns="fairCols" class="tbl">
            <template #dimension-cell="{ row }">
              <span class="text-muted font-semibold">{{ firstOfDim(row.index) ? dims[row.original.dimension] : '' }}</span>
            </template>
            <template #band-cell="{ row }">
              <CvTag :kind="row.original.withinBand ? 'fast' : 'urgent'" :icon="row.original.withinBand ? 'check' : 'urgent'">
                {{ row.original.withinBand ? 'Inside' : 'Outside' }}
              </CvTag>
            </template>
          </UTable>
          <p class="note">
            <UIcon name="i-lucide-shield-check" class="size-4 shrink-0" />{{ fairness.note }}
          </p>
        </div>
      </section>

      <section class="sec" aria-labelledby="fs-versions">
        <span class="no num" aria-hidden="true">{{ nVersions }}</span>
        <h2 id="fs-versions">
          Versions and sign-offs
        </h2>
        <div class="body">
          <UTimeline :items="versionItems" color="neutral" size="sm" class="versions" :ui="{ title: 'font-round text-[17px] font-semibold [font-variation-settings:\'FLAR\'_100]', date: 'text-[13px] text-muted', wrapper: 'pb-5' }">
            <template #description="{ item }">
              <p class="m-0 text-muted text-[13.5px]">
                {{ item.description }}
              </p>
              <ul class="so">
                <li v-for="s in item.version.signOffs" :key="s.side">
                  <CvTag :kind="s.state === 'signed' ? 'fast' : 'plain'" :icon="s.state === 'signed' ? 'check' : 'clock'">
                    {{ s.sideLabel }}: {{ s.state === 'signed' ? `${s.by?.name}, ${s.at ? fmtDayShort(s.at) : ''}` : 'waiting' }}
                  </CvTag>
                </li>
              </ul>
            </template>
          </UTimeline>
        </div>
      </section>

      <section v-if="tech" class="sec tech" aria-label="For the technical reviewer">
        <span class="no num" aria-hidden="true">{{ nVersions + 1 }}</span>
        <UAccordion :items="techItems" :ui="{ trigger: 'py-0 text-[22px] font-round font-semibold [font-variation-settings:\'FLAR\'_100]', item: 'border-0' }">
          <template #tech>
            <div class="body pt-4">
              <p v-for="(b, i) in fold?.body ?? []" :key="i" class="muted">
                {{ b }}
              </p>
              <p class="muted">
                {{ tech.split }}
              </p>
              <UTable :data="metricRows" :columns="metricCols" class="tbl" />
              <h3>Calibration: predicted vs what happened</h3>
              <div class="calib" role="img" :aria-label="tech.calibration.map(c => `predicted ${pct(c.predicted, 0)}, observed ${pct(c.observed, 0)}`).join('; ')">
                <span v-for="(c, i) in tech.calibration" :key="i" class="cb">
                  <i class="p" :style="{ height: `${c.predicted * 100}%` }" /><i class="o" :style="{ height: `${c.observed * 100}%` }" />
                </span>
              </div>
              <p class="legend muted">
                <span><i class="p" />Predicted</span><span><i class="o" />What happened</span>
              </p>
              <UTable :data="tech.calibration" :columns="calCols" class="tbl" />
              <h3>What it looks at</h3>
              <p class="muted">
                {{ tech.features.join(' · ') }}
              </p>
            </div>
          </template>
        </UAccordion>
      </section>
    </article>

    <div v-else-if="!error" class="doc" aria-busy="true" aria-label="Loading the fact sheet">
      <USkeleton v-for="n in 4" :key="n" class="h-40 w-full rounded-[28px]" />
    </div>
  </div>
</template>

<style scoped>
.doc { display: grid; gap: 14px; }
.sec {
  display: grid; gap: 10px 24px; padding: 22px 24px; border-radius: 28px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft);
  grid-template-columns: 48px minmax(180px, 280px) minmax(0, 1fr); align-items: start;
}
.no { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; font-family: var(--font-round); font-size: 20px; font-weight: 900; background: var(--cv-jade-wash); color: var(--cv-jade-ink); }
.sec h2 { font-size: 23px; font-weight: 900; line-height: 1.15; padding-top: 6px; }
.body { min-width: 0; display: grid; gap: 10px; max-width: 980px; padding-top: 6px; }
.body p, .body li { font-size: 15.5px; line-height: 1.6; margin: 0; }
.body ul { margin: 0; padding-left: 20px; display: grid; gap: 4px; }
.body li::marker { color: var(--cv-jade); }
.tech { grid-template-columns: 48px minmax(0, 1fr); }
.tech .body { max-width: none; }
.muted, .body p.muted { color: var(--cv-muted); font-size: 14px; }
.body h3 { font-family: var(--font-sans); font-size: 13px; font-weight: 500; color: var(--cv-muted); margin: 10px 0 0; letter-spacing: 0; }
.note { display: flex; gap: 6px; align-items: flex-start; font-size: 13px !important; color: var(--cv-muted); }
.so { list-style: none; margin: 6px 0 0; padding: 0; display: flex; gap: 6px; flex-wrap: wrap; }
.calib { display: flex; gap: 6px; align-items: flex-end; height: 100px; max-width: 640px; border-bottom: 2px solid var(--cv-rule); }
.cb { flex: 1; display: flex; gap: 3px; align-items: flex-end; height: 100%; }
.cb i { display: inline-block; width: 50%; border-radius: 999px 999px 3px 3px; }
.p { background: var(--cv-faint); }
.o { background: var(--cv-jade); }
.legend { display: flex; gap: 14px; }
.legend span { display: inline-flex; gap: 6px; align-items: center; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
@media (max-width: 1100px) {
  .sec { grid-template-columns: 48px minmax(0, 1fr); }
  .sec > .body { grid-column: 2; }
}
@media (max-width: 720px) {
  .sec { padding: 16px; grid-template-columns: 36px minmax(0, 1fr); gap: 8px 12px; border-radius: 24px; }
  .sec > .body { grid-column: 1 / -1; }
  .no { width: 34px; height: 34px; font-size: 16px; }
  .sec h2 { font-size: 20px; padding-top: 3px; }
}
</style>
