<script setup lang="ts">
// One of the four questions a regulator asks, answered in a sentence with one chart under it. Charts are
// single-series: "ours" in orchid, comparison in faint grey with a direct label; the text never takes a series colour.
import type { Question } from '~/types/api'
import { emphasis, fmtDayShort, frequency, pct } from '~/utils/format'
import { statusStyle } from '~/utils/labels'

const props = withDefaults(defineProps<{ q: Question, tint?: boolean }>(), { tint: false })
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
</script>

<template>
  <section class="q" :class="{ tint }" :aria-labelledby="`q-${q.key}`">
    <div class="ask">
      <i aria-hidden="true" />{{ q.question }}
    </div>
    <h3 :id="`q-${q.key}`">
      <template v-for="(s, i) in answer" :key="i">
        <b v-if="s.em">{{ s.text }}</b><template v-else>
          {{ s.text }}
        </template>
      </template>
    </h3>

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
            <span class="v num">{{ pct(d.rate) }}<CvIcon v-if="!d.withinBand" name="urgent" size="s" /></span>
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

    <table v-if="q.compare?.length" class="cc">
      <thead><tr><th><span class="sr-only-cv">Measure</span></th><th>In use</th><th>On trial</th></tr></thead>
      <tbody>
        <tr v-for="r in q.compare" :key="r.key">
          <td>{{ r.label }}</td><td><b>{{ r.inUse }}</b></td><td><b :class="{ better: r.better }">{{ r.candidate }}</b><CvIcon v-if="r.better" name="check" size="s" class="better" /></td>
        </tr>
      </tbody>
    </table>
    <div v-if="q.signOffs?.length" class="signs">
      <CvTag v-for="s in q.signOffs" :key="s.side" :kind="s.state === 'signed' ? 'fast' : 'plain'" :icon="s.state === 'signed' ? 'check' : 'clock'">
        {{ s.sideLabel }}: {{ s.by?.name ?? 'waiting' }}<template v-if="s.state === 'signed' && s.at">
          , {{ fmtDayShort(s.at).replace(/^\w+ /, '') }}
        </template>
      </CvTag>
      <button v-if="can('models:signoff') && waiting" class="btn primary sm" type="button" @click="$emit('signoff')">
        Review and sign off
      </button>
    </div>

    <p class="foot">
      <CvIcon :name="q.key === 'fair' ? 'shield' : q.key === 'like_learned' ? 'clock' : 'check'" size="s" />{{ q.foot }}
    </p>
  </section>
</template>

<style scoped>
.q { background: var(--cv-surface); border-radius: 28px; padding: 20px 22px 18px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.q.tint { background: var(--cv-sunk); }
.ask { font-size: 13px; font-weight: 750; color: var(--cv-muted); display: flex; align-items: center; gap: 7px; }
.ask i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-caller); }
h3 { font-size: 24px; font-weight: 650; letter-spacing: -0.025em; line-height: 1.2; }
h3 b { color: var(--cv-orchid-ink); font-weight: 750; }
.hb { display: grid; grid-template-columns: 170px 1fr 92px; gap: 8px 12px; align-items: center; font-size: 13.5px; }
.track { height: 14px; position: relative; }
.fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 0 4px 4px 0; background: var(--cv-faint); }
.fill.us { background: var(--cv-orchid); }
.hb b { font-weight: 750; text-align: right; }
.fair { display: grid; grid-template-columns: 112px 1fr 64px; gap: 2px 12px; align-items: center; font-size: 13px; }
.g { color: var(--cv-muted); font-size: 11.5px; font-weight: 750; grid-column: 1 / -1; margin-top: 4px; }
.lane { position: relative; height: 22px; }
.lane::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: var(--cv-sunk-2); }
.band { position: absolute; top: 0; bottom: 0; background: var(--cv-fast-wash); border-radius: 6px; }
.mid { position: absolute; top: -2px; bottom: -2px; width: 2px; margin-left: -1px; background: var(--cv-fast); border-radius: 1px; }
.dot { position: absolute; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: var(--cv-ink); box-shadow: 0 0 0 2px var(--cv-surface); }
.dot.out { background: var(--cv-urgent); }
.v { font-weight: 700; text-align: right; display: inline-flex; gap: 3px; align-items: center; justify-content: flex-end; }
.axis { display: grid; grid-template-columns: 112px 1fr 64px; gap: 12px; font-size: 11.5px; color: var(--cv-faint); font-weight: 650; }
.axis div { display: flex; justify-content: space-between; }
.drift { display: grid; grid-template-columns: 1fr 98px; gap: 12px; align-items: end; }
.cols8 { position: relative; height: 128px; display: flex; align-items: flex-end; gap: 10px; padding: 0 4px; }
.lim { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--cv-sunk-2); font-size: 11px; color: var(--cv-muted); font-weight: 650; }
.lim span { position: absolute; left: 0; top: -16px; }
.lim.act { border-top-color: color-mix(in srgb, var(--cv-urgent) 40%, transparent); }
.c { flex: 1; max-width: 24px; margin: 0 auto; border-radius: 4px 4px 0 0; background: var(--cv-faint); min-height: 4px; }
.c.watch.now, .c.watch { background: var(--cv-siu); }
.c.act { background: var(--cv-urgent); }
.wk { display: flex; gap: 10px; padding: 0 4px; font-size: 11px; color: var(--cv-faint); font-weight: 650; }
.wk span { flex: 1; text-align: center; white-space: nowrap; }
.state { display: grid; gap: 6px; }
.cc { width: 100%; border-collapse: separate; border-spacing: 0 6px; font-size: 14px; }
.cc th { text-align: left; font-size: 12.5px; color: var(--cv-muted); font-weight: 750; padding: 0 10px; }
.cc td { background: var(--cv-surface); padding: 9px 10px; }
.cc td:first-child { border-radius: 12px 0 0 12px; color: var(--cv-muted); }
.cc td:last-child { border-radius: 0 12px 12px 0; }
.cc .better { color: var(--cv-fast); font-weight: 750; vertical-align: -2px; margin-left: 4px; }
.signs { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; font-size: 13.5px; }
.signs .btn { margin-left: auto; }
.foot { font-size: 13px; color: var(--cv-muted); display: flex; gap: 6px; align-items: flex-start; margin: auto 0 0; }
.foot :deep(svg) { margin-top: 2px; }
@media (max-width: 720px) {
  .hb { grid-template-columns: 1fr 72px; }
  .hb > span:not(.track) { grid-column: 1 / -1; margin-bottom: -6px; }
  .fair { grid-template-columns: 84px 1fr 52px; }
  .axis { grid-template-columns: 84px 1fr 52px; }
  .drift { grid-template-columns: 1fr; }
  .state { display: flex; flex-wrap: wrap; }
}
</style>
