<script setup lang="ts">
// A routing check's fact sheet: what it's for and not for, what it looks at (in words), how it was tested, known
// limits, fairness results and the sign-off history, with the technical measures folded away for the reviewer.
import type { FactSheet, Fairness } from '~/types/api'
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

const main = computed(() => (sheet.value?.sections ?? []).filter(s => s.key !== 'technical'))
const fold = computed(() => sheet.value?.sections.find(s => s.key === 'technical') ?? null)
const tech = computed(() => sheet.value?.technical ?? null)
const metricRows = computed(() => {
  const t = tech.value
  if (!t) return []
  const rows: { name: string, m: typeof t.test }[] = [{ name: 'Gradient-boosted trees (in use)', m: t.test }]
  if (t.randomForest) rows.push({ name: 'Random forest (challenger)', m: t.randomForest })
  rows.push({ name: 'Logistic baseline', m: t.baseline })
  return rows
})
const dims = { region: 'Region', language: 'Language of the call', age_band: 'Age of policyholder' } as const
const two = (n: number) => n.toFixed(2)
</script>

<template>
  <div>
    <PageHeader :title="sheet?.name ?? 'Fact sheet'" :caption="sheet ? `Fact sheet · version ${sheet.version}` : ''" :back="{ to: '/routing', label: 'Routing checks' }">
      <div class="seg hide-phone" role="group" aria-label="Which check">
        <NuxtLink to="/routing/size" :aria-current="key === 'size' ? 'page' : undefined">Size check</NuxtLink>
        <NuxtLink to="/routing/closer_look" :aria-current="key === 'closer_look' ? 'page' : undefined">Closer-look check</NuxtLink>
      </div>
    </PageHeader>
    <StateNote v-if="error" kind="error" title="We couldn't load this fact sheet." :body="error" retry class="wrap" @retry="load" />
    <main v-if="sheet" class="sheet wrap">
      <article class="card body">
        <section v-for="s in main" :key="s.key" class="sec">
          <h2>{{ s.title }}</h2>
          <ul v-if="s.body.length > 1">
            <li v-for="(b, i) in s.body" :key="i">
              {{ b }}
            </li>
          </ul>
          <p v-else>
            {{ s.body[0] }}
          </p>
        </section>
        <details v-if="tech" class="fold">
          <summary>For the technical reviewer</summary>
          <p v-for="(b, i) in fold?.body ?? []" :key="i" class="muted">
            {{ b }}
          </p>
          <p class="muted">
            {{ tech.split }}
          </p>
          <table class="mt">
            <thead><tr><th>Measured on the test period</th><th>Area under ROC</th><th>Area under precision–recall</th><th>Brier</th><th>Calibration error</th></tr></thead>
            <tbody>
              <tr v-for="r in metricRows" :key="r.name">
                <td>{{ r.name }}</td><td class="num">{{ two(r.m.auc) }}</td><td class="num">{{ two(r.m.prAuc) }}</td><td class="num">{{ two(r.m.brier) }}</td><td class="num">{{ two(r.m.ece) }}</td>
              </tr>
            </tbody>
          </table>
          <h3>Calibration: predicted vs what happened</h3>
          <div class="calib" role="img" :aria-label="tech.calibration.map(c => `predicted ${pct(c.predicted, 0)}, observed ${pct(c.observed, 0)}`).join('; ')">
            <span v-for="(c, i) in tech.calibration" :key="i" class="cb">
              <i class="p" :style="{ height: `${c.predicted * 100}%` }" /><i class="o" :style="{ height: `${c.observed * 100}%` }" />
            </span>
          </div>
          <p class="legend muted">
            <span><i class="p" />Predicted</span><span><i class="o" />What happened</span>
          </p>
          <h3>What it looks at</h3>
          <p class="muted">
            {{ tech.features.join(' · ') }}
          </p>
        </details>
      </article>
      <aside class="side">
        <section v-if="fairness" class="card tint">
          <h2>Fairness, version {{ fairness.version }}</h2>
          <p class="muted">
            Overall {{ pct(fairness.overallRate) }}; the allowed band is {{ (fairness.band * 100).toFixed(1) }} points either side.
          </p>
          <table class="ft">
            <tbody>
              <template v-for="(name, d) in dims" :key="d">
                <tr><th colspan="3">{{ name }}</th></tr>
                <tr v-for="r in fairness.rows.filter(x => x.dimension === d)" :key="r.group">
                  <td>{{ r.label }}</td><td class="num">{{ pct(r.flaggedRate) }}</td>
                  <td><CvTag :kind="r.withinBand ? 'fast' : 'urgent'" :icon="r.withinBand ? 'check' : 'urgent'">{{ r.withinBand ? 'Inside' : 'Outside' }}</CvTag></td>
                </tr>
              </template>
            </tbody>
          </table>
          <p class="note">
            <CvIcon name="shield" size="s" />{{ fairness.note }}
          </p>
        </section>
        <section class="card">
          <h2>Versions and sign-offs</h2>
          <ol class="versions">
            <li v-for="v in sheet.versions" :key="v.version">
              <b>Version {{ v.version }}</b>
              <CvTag :kind="v.stage === 'in_use' ? 'fast' : v.stage === 'candidate' ? 'orchid' : 'plain'" :icon="v.stage === 'in_use' ? 'check' : 'clock'">
                {{ v.stage === 'in_use' ? `In use${v.inUseSince ? ` since ${fmtDate(v.inUseSince)}` : ''}` : v.stage === 'candidate' ? 'On trial' : 'Retired' }}
              </CvTag>
              <span class="muted">{{ v.trainedOn }}</span>
              <span v-for="s in v.signOffs" :key="s.side" class="so" :class="s.state">
                <CvIcon :name="s.state === 'signed' ? 'check' : 'clock'" size="s" />{{ s.sideLabel }}: {{ s.state === 'signed' ? `${s.by?.name}, ${s.at ? fmtDayShort(s.at) : ''}` : 'waiting' }}
              </span>
            </li>
          </ol>
        </section>
      </aside>
    </main>
    <div v-else-if="!error" class="sheet wrap" aria-busy="true">
      <span class="skeleton" style="height: 600px; border-radius: 28px" /><span class="skeleton" style="height: 400px; border-radius: 28px" />
    </div>
  </div>
</template>

<style scoped>
.wrap { margin-left: 32px; margin-right: 32px; }
.sheet { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.card { padding: 22px 24px; }
.body { display: grid; gap: 18px; }
.sec h2, .side h2 { font-size: 21px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 6px; }
.sec p, .sec li { font-size: 15.5px; line-height: 1.55; }
.sec ul { margin: 0; padding-left: 20px; display: grid; gap: 4px; }
.muted { color: var(--cv-muted); font-size: 14px; }
.fold { background: var(--cv-sunk); border-radius: 20px; padding: 12px 16px; }
.fold summary { cursor: pointer; font-weight: 700; font-family: var(--font-display); font-size: 17px; }
.fold h3 { font-family: var(--font-sans); font-size: 13px; font-weight: 750; color: var(--cv-muted); margin: 14px 0 6px; letter-spacing: 0; }
.mt, .ft { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 8px; }
.mt th { text-align: left; font-size: 12px; color: var(--cv-muted); font-weight: 700; padding: 4px 6px; }
.mt td { padding: 6px; border-top: 1px solid var(--cv-sunk-2); }
.calib { display: flex; gap: 6px; align-items: flex-end; height: 100px; }
.cb { flex: 1; display: flex; gap: 2px; align-items: flex-end; height: 100%; }
.cb i, .legend i { display: inline-block; width: 50%; border-radius: 3px 3px 0 0; }
.p { background: var(--cv-faint); } .o { background: var(--cv-orchid); }
.legend { display: flex; gap: 14px; } .legend span { display: inline-flex; gap: 6px; align-items: center; } .legend i { width: 10px; height: 10px; border-radius: 3px; }
.side { display: grid; gap: 16px; }
.ft th { text-align: left; font-size: 12px; color: var(--cv-muted); font-weight: 750; padding: 10px 0 4px; }
.ft td { padding: 4px 0; }
.ft td:nth-child(2) { font-weight: 700; text-align: right; padding-right: 12px; }
.ft td:last-child { text-align: right; }
.note { display: flex; gap: 6px; align-items: flex-start; font-size: 13px; color: var(--cv-muted); margin: 12px 0 0; }
.versions { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.versions li { display: grid; gap: 6px; justify-items: start; padding-bottom: 12px; border-bottom: 1px solid var(--cv-sunk); }
.so { display: inline-flex; gap: 6px; align-items: center; font-size: 13.5px; font-weight: 600; }
.so.signed { color: var(--cv-fast); } .so.waiting { color: var(--cv-muted); }
@media (max-width: 1100px) { .sheet { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .wrap { margin-left: 16px; margin-right: 16px; } .mt { display: block; overflow-x: auto; } }
</style>
