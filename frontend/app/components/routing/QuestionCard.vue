<script setup lang="ts">
// One of the four questions a regulator asks, as an answer card (DESIGN.md §3): the question as its heading, the
// answer as a big sentence in frequencies (with a 100-dot picture when the answer is a share), its one chart beside
// it, the foot note under both. Charts are single-series: "ours" in jade, comparison in faint grey with a direct
// label; text never takes a series colour.
import type { TableColumn } from '@nuxt/ui'
import type { CompareRow, Question } from '~/types/api'
import { emphasis, fmtDayShort, frequency, pct } from '~/utils/format'
import { statusStyle } from '~/utils/labels'

const props = defineProps<{ q: Question, n: number }>()
defineEmits<{ signoff: [] }>()
const { can } = useSession()
const answer = computed(() => emphasis(props.q.answer))
const barText = (v: number) => (v > 1 ? String(v) : frequency(v, v >= 0.1 && Math.round(v * 10) === v * 10 ? 10 : 100))

// Fairness: scale the axis to fit the band and every group.
const fairMax = computed(() => {
  const vals = [...(props.q.dots ?? []).map(d => d.rate), (props.q.overallRate ?? 0) + (props.q.band ?? 0)]
  return Math.max(0.1, Math.ceil(Math.max(...vals) * 40) / 40)
})
const fairGroups = computed(() => {
  const order = ['region', 'language', 'age_band'] as const
  const names = { region: 'Region', language: 'Language of the call', age_band: 'Age of policyholder' }
  return order.map(d => ({ key: d, name: names[d], dots: (props.q.dots ?? []).filter(x => x.dimension === d) })).filter(g => g.dots.length)
})
const x = (v: number) => `${(v / fairMax.value) * 100}%`
const ticks = computed(() => [0, 0.25, 0.5, 0.75, 1].map(f => f * fairMax.value))

// Drift: columns against Watch (0.10) and Act (0.25).
const driftMax = 0.3
const weeks = computed(() => props.q.weeks ?? [])
const waiting = computed(() => (props.q.signOffs ?? []).some(s => s.state === 'waiting'))
// The 100-dot picture: the share in the answer, as filled dots out of 100.
const share = computed(() => props.q.bars?.find(b => b.ours && b.value > 0 && b.value <= 1)?.value ?? null)
const filled = computed(() => (share.value == null ? 0 : Math.round(share.value * 100)))

const compareCols: TableColumn<CompareRow>[] = [
  { accessorKey: 'label', header: 'Measure' },
  { accessorKey: 'inUse', header: 'In use' },
  { accessorKey: 'candidate', header: 'On trial' },
]
</script>

<template>
  <li class="q" :aria-labelledby="`q-${q.key}`">
    <span class="no num" aria-hidden="true">{{ n }}</span>
    <h2 :id="`q-${q.key}`" class="ask">
      {{ q.question }}
    </h2>

    <div class="answer">
      <div v-if="share != null" class="dots" role="img" :aria-label="`${filled} in 100`">
        <i v-for="d in 100" :key="d" :class="{ on: d <= filled }" />
      </div>
      <p class="said">
        <template v-for="(s, i) in answer" :key="i">
          <b v-if="s.em">{{ s.text }}</b><template v-else>
            {{ s.text }}
          </template>
        </template>
      </p>
      <div v-if="q.signOffs?.length" class="signs">
        <CvTag v-for="s in q.signOffs" :key="s.side" :kind="s.state === 'signed' ? 'fast' : 'plain'" :icon="s.state === 'signed' ? 'check' : 'clock'">
          {{ s.sideLabel }}: {{ s.by?.name ?? 'waiting' }}<template v-if="s.state === 'signed' && s.at">
            , {{ fmtDayShort(s.at).replace(/^\w+ /, '') }}
          </template>
        </CvTag>
        <UButton v-if="can('models:signoff') && waiting" icon="i-lucide-pen-line" @click="$emit('signoff')">
          Review and sign off
        </UButton>
      </div>
    </div>

    <div class="chart">
      <div v-if="q.bars?.length" class="hb" role="img" :aria-label="q.bars.map(b => `${b.label}: ${barText(b.value)}`).join('; ')">
        <template v-for="b in q.bars" :key="b.label">
          <span>{{ b.label }}</span>
          <span class="track"><span class="fill" :class="{ us: b.ours }" :style="{ width: `${Math.min(1, b.value > 1 ? b.value / 10 : b.value) * 100}%` }" /></span>
          <b class="num">{{ barText(b.value) }}</b>
        </template>
      </div>

      <template v-if="fairGroups.length">
        <div class="fair" role="img" :aria-label="`Share of claims sent for a closer look by group. Overall ${pct(q.overallRate ?? 0)}. Allowed band ${pct((q.overallRate ?? 0) - (q.band ?? 0))} to ${pct((q.overallRate ?? 0) + (q.band ?? 0))}. ${(q.dots ?? []).map(d => `${d.label} ${pct(d.rate)}${d.withinBand ? '' : ', outside the band'}`).join(', ')}.`">
          <template v-for="g in fairGroups" :key="g.key">
            <span class="g">{{ g.name }}</span>
            <template v-for="d in g.dots" :key="d.group">
              <span class="lab">{{ d.label }}</span>
              <span class="lane">
                <span class="band" :style="{ left: x((q.overallRate ?? 0) - (q.band ?? 0)), width: x((q.band ?? 0) * 2) }" />
                <span class="mid" :style="{ left: x(q.overallRate ?? 0) }" />
                <span class="dot" :class="{ out: !d.withinBand }" :style="{ left: x(d.rate) }" :title="`${d.label} ${pct(d.rate)} of ${d.count} claims`" />
              </span>
              <span class="v num">{{ pct(d.rate) }}<UIcon v-if="!d.withinBand" name="i-lucide-triangle-alert" class="size-3.5" /></span>
            </template>
          </template>
        </div>
        <div class="axis num" aria-hidden="true">
          <span /><div><span v-for="tk in ticks" :key="tk">{{ pct(tk, tk === 0 ? 0 : 1) }}</span></div><span />
        </div>
      </template>

      <div v-if="weeks.length" class="drift">
        <div>
          <div class="cols8" role="img" :aria-label="`How different each week's calls are, last ${weeks.length} weeks: ${weeks.map(w => `${w.label} ${w.status}`).join(', ')}.`">
            <span class="lim" :style="{ bottom: `${(0.1 / driftMax) * 100}%` }"><span>Watch</span></span>
            <span class="lim act" :style="{ bottom: `${(0.25 / driftMax) * 100}%` }"><span>Act</span></span>
            <span v-for="(w, i) in weeks" :key="w.label" class="c" :class="[w.status, { now: i === weeks.length - 1 }]" :style="{ height: `${Math.min(1, w.psi / driftMax) * 100}%` }" :title="`${w.label}: ${w.status === 'stable' ? 'fine' : w.status}`" />
          </div>
          <div class="wk num">
            <span v-for="w in weeks" :key="w.label">{{ w.label.replace(/^Week of /, '') }}</span>
          </div>
        </div>
        <div class="state">
          <CvTag v-for="s in (['stable', 'watch', 'act'] as const)" :key="s" :kind="statusStyle(s).kind" :icon="statusStyle(s).icon">
            {{ s === 'stable' ? 'Fine' : s === 'watch' ? 'Watch' : 'Act' }}
          </CvTag>
        </div>
      </div>

      <UTable v-if="q.compare?.length" :data="q.compare" :columns="compareCols" class="cc">
        <template #label-cell="{ row }">
          <span class="text-muted">{{ row.original.label }}</span>
        </template>
        <template #inUse-cell="{ row }">
          <b class="num">{{ row.original.inUse }}</b>
        </template>
        <template #candidate-cell="{ row }">
          <span class="inline-flex items-center gap-1">
            <b class="num" :class="{ better: row.original.better }">{{ row.original.candidate }}</b>
            <UIcon v-if="row.original.better" name="i-lucide-check" class="size-4 better" />
            <span v-if="row.original.better" class="sr-only-cv">, better</span>
          </span>
        </template>
      </UTable>
    </div>

    <p class="foot">
      <UIcon v-if="q.key === 'fair'" name="i-lucide-shield-check" class="size-4 shrink-0" />
      <UIcon v-else-if="q.key === 'like_learned'" name="i-lucide-clock" class="size-4 shrink-0" />
      <UIcon v-else name="i-lucide-check" class="size-4 shrink-0" />{{ q.foot }}
    </p>
  </li>
</template>

<style scoped>
.q {
  display: grid; gap: 14px 36px; padding: 26px 28px 22px; border-radius: 32px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft);
  grid-template-columns: 52px minmax(0, 1fr) minmax(0, 1.1fr);
  grid-template-areas: "no ask ask" "no answer chart" "no foot foot";
}
.no { grid-area: no; width: 48px; height: 48px; border-radius: 50%; display: grid; place-items: center; font-family: var(--font-round); font-size: 22px; font-weight: 900; background: var(--cv-jade-wash); color: var(--cv-jade-ink); }
.ask { grid-area: ask; font-size: 28px; font-weight: 900; line-height: 1.12; align-self: center; letter-spacing: -0.02em; }
.answer { grid-area: answer; display: grid; gap: 16px; align-content: start; }
.said { margin: 0; font-family: var(--font-round); font-size: 23px; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; }
.said b { color: var(--cv-jade-ink); font-weight: 900; }
.dots { display: grid; grid-template-columns: repeat(20, 12px); gap: 5px; }
.dots i { width: 12px; height: 12px; border-radius: 50%; background: var(--cv-sunk-2); }
.dots i.on { background: var(--cv-jade); }
.chart { grid-area: chart; min-width: 0; display: grid; gap: 8px; align-content: start; padding: 16px 18px; border-radius: 24px; background: var(--cv-bg); }
.foot { grid-area: foot; font-size: 13px; color: var(--cv-muted); display: flex; gap: 6px; align-items: flex-start; margin: 2px 0 0; }
.foot :deep(svg), .foot > span:first-child { margin-top: 2px; }
.hb { display: grid; grid-template-columns: 170px 1fr 92px; gap: 10px 12px; align-items: center; font-size: 13.5px; }
.track { height: 16px; position: relative; border-radius: 999px; background: var(--cv-sunk); }
.fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px; background: var(--cv-faint); }
.fill.us { background: var(--cv-jade); }
.hb b { font-weight: 600; text-align: right; }
.fair { display: grid; grid-template-columns: 112px 1fr 64px; gap: 2px 12px; align-items: center; font-size: 13px; }
.g { color: var(--cv-muted); font-size: 12.5px; font-weight: 600; grid-column: 1 / -1; margin-top: 6px; }
.lane { position: relative; height: 24px; }
.lane::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 2px; margin-top: -1px; border-radius: 2px; background: var(--cv-sunk-2); }
.band { position: absolute; top: 2px; bottom: 2px; background: var(--cv-fast-wash); border-radius: 999px; }
.mid { position: absolute; top: 0; bottom: 0; width: 3px; margin-left: -1.5px; background: var(--cv-fast); border-radius: 2px; }
.dot { position: absolute; top: 50%; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%; background: var(--cv-ink); box-shadow: 0 0 0 3px var(--cv-bg); }
.dot.out { background: var(--cv-urgent); }
.v { font-weight: 600; text-align: right; display: inline-flex; gap: 3px; align-items: center; justify-content: flex-end; }
.v :deep(svg), .v > span { color: var(--cv-urgent); }
.axis { display: grid; grid-template-columns: 112px 1fr 64px; gap: 12px; font-size: 11.5px; color: var(--cv-muted); font-weight: 500; }
.axis div { display: flex; justify-content: space-between; }
.drift { display: grid; grid-template-columns: minmax(0, 1fr) 98px; min-width: 0; gap: 12px; align-items: end; }
.cols8 { position: relative; height: 140px; display: flex; align-items: flex-end; gap: 10px; padding: 0 4px; border-bottom: 2px solid var(--cv-rule); }
.lim { position: absolute; left: 0; right: 0; border-top: 2px dashed var(--cv-sunk-2); font-size: 11px; color: var(--cv-muted); font-weight: 500; }
.lim span { position: absolute; left: 0; top: -17px; }
.lim.act { border-top-color: color-mix(in srgb, var(--cv-urgent) 40%, transparent); }
.c { flex: 1; max-width: 26px; margin: 0 auto; border-radius: 999px 999px 4px 4px; background: var(--cv-faint); min-height: 6px; }
.c.watch { background: var(--cv-siu); }
.c.act { background: var(--cv-urgent); }
.wk { display: flex; gap: 10px; padding: 4px 4px 0; font-size: 11px; color: var(--cv-muted); font-weight: 500; }
.wk span { flex: 1; min-width: 0; text-align: center; white-space: nowrap; overflow: hidden; }
.state { display: grid; gap: 6px; }
.better { color: var(--cv-fast); }
.signs { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; font-size: 13.5px; }
@media (max-width: 1100px) {
  .q { grid-template-columns: 52px minmax(0, 1fr); grid-template-areas: "no ask" "answer answer" "chart chart" "foot foot"; }
}
@media (max-width: 720px) {
  .q { padding: 18px 16px 16px; gap: 12px; grid-template-columns: 40px minmax(0, 1fr); border-radius: 26px; }
  .no { width: 38px; height: 38px; font-size: 18px; }
  .ask { font-size: 21px; }
  .said { font-size: 19px; }
  .dots { grid-template-columns: repeat(20, 9px); gap: 4px; }
  .dots i { width: 9px; height: 9px; }
  .chart { padding: 12px; }
  .hb { grid-template-columns: 1fr 72px; }
  .hb > span:not(.track) { grid-column: 1 / -1; margin-bottom: -6px; }
  .fair { grid-template-columns: 84px 1fr 52px; }
  .axis { grid-template-columns: 84px 1fr 52px; }
  .drift { grid-template-columns: minmax(0, 1fr); }
  .cols8, .wk { gap: 4px; }
  .wk { font-size: 10px; }
  .state { display: flex; flex-wrap: wrap; }
}
</style>
