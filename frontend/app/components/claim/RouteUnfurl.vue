<script setup lang="ts">
// The verdict (DESIGN.md §9): where the claim goes, as a big word with its icon, then three plain reasons as numbered
// pebbles, each with the moment it was heard (▸ plays the recording from there). Reduced motion: appears complete.
import type { RoutingDecision } from '~/types/api'
import { fmtClock } from '~/utils/format'
import { routeStyle } from '~/utils/labels'
import { icon } from '~/utils/icons'

const props = withDefaults(defineProps<{ decision: RoutingDecision, siuOpen?: boolean, compact?: boolean }>(), { siuOpen: false, compact: false })
const emit = defineEmits<{ seek: [seconds: number] }>()
const whyTitle = computed(() => {
  const r = props.decision.route
  if (r === 'fast_track') return 'Why fast-track'
  if (r === 'adjuster') return 'Why an adjuster, not fast-track'
  return 'Why a closer look'
})
const showSiu = computed(() => props.siuOpen && props.decision.route !== 'special_investigation')
const style = computed(() => routeStyle(props.decision.route))
</script>

<template>
  <div class="verdict" :class="[`k-${style.kind}`, { compact }]">
    <div class="vhead">
      <span class="vic" aria-hidden="true"><UIcon :name="icon(style.icon)" /></span>
      <p class="vword round">
        {{ decision.routeLabel }}<template v-if="showSiu">
          <span class="and">, and a closer look</span>
        </template>
      </p>
    </div>
    <slot name="note" />
    <h4 class="whyh">
      {{ whyTitle }}
    </h4>
    <ol class="why">
      <li v-for="(r, i) in decision.reasons" :key="r.feature" :style="{ animationDelay: `${200 + i * 90}ms` }">
        <span class="n num round">{{ i + 1 }}</span>
        <span class="txt">{{ r.text }}</span>
        <button v-if="r.atSeconds != null" class="heard chip" type="button" :aria-label="`Play from ${fmtClock(r.atSeconds)}`" @click="emit('seek', r.atSeconds!)">
          <span class="at"><UIcon name="i-lucide-play" class="tri" />{{ fmtClock(r.atSeconds) }}</span>
        </button>
      </li>
    </ol>
    <p v-if="decision.rulesApplied.length" class="rules">
      <UIcon name="i-lucide-check" class="size-4" />{{ decision.rulesApplied.join(' · ') }}
    </p>
  </div>
</template>

<style scoped>
.vhead { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.vic { width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; font-size: 28px; flex: none; animation: pop var(--m-pop) var(--ease-tide) both; }
.k-fast .vic { background: var(--cv-jade); color: var(--cv-on-jade); }
.k-adj .vic { background: var(--cv-person); color: #fff; }
.k-siu .vic { background: var(--cv-siu); color: #fff; }
[data-theme="dark"] .k-adj .vic, [data-theme="dark"] .k-siu .vic { color: var(--cv-bg); }
.vword { margin: 0; font-size: 44px; line-height: 1; font-weight: 900; letter-spacing: -0.025em; text-shadow: 0 0.055em 0 var(--cv-cushion); }
.compact .vword { font-size: 32px; }
.and { color: var(--cv-siu); }
.whyh { font-family: var(--font-sans); font-size: 13px; font-weight: 500; color: var(--cv-muted); margin: 18px 0 8px; }
.why { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); gap: 10px; }
.why li {
  display: grid; grid-template-columns: auto minmax(0, 1fr); grid-template-rows: auto auto; gap: 6px 12px; align-items: start;
  padding: 14px 16px; border-radius: 22px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); font-size: 15px; line-height: 1.4;
  animation: rise 320ms var(--ease-tide) both;
}
.n { grid-row: span 2; width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; font-weight: 900; font-size: 16px; }
.k-adj .n { background: var(--cv-adj-wash); color: var(--cv-adj); }
.k-fast .n { background: var(--cv-fast-wash); color: var(--cv-fast); }
.k-siu .n { background: var(--cv-siu-wash); color: var(--cv-siu); }
.chip { justify-self: start; min-height: 0; padding: 2px; border-width: 0; background: none; }
.chip .at { height: 24px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.rules { margin: 12px 0 0; font-size: 13px; color: var(--cv-muted); display: flex; gap: 6px; align-items: center; }
.compact .why li { font-size: 14px; padding: 12px 14px; }
@media (max-width: 720px) { .vword { font-size: 34px; } .vic { width: 48px; height: 48px; font-size: 24px; } }
</style>
