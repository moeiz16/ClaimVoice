<script setup lang="ts">
// Route reveal: the route tag unfurls (clip-path, 600 ms) and three plain reasons stagger in (90 ms), each with the
// moment it was heard as a ▸ chip that plays the tape from there. Reduced motion: appears complete.
import type { RoutingDecision } from '~/types/api'
import { fmtClock } from '~/utils/format'

const props = withDefaults(defineProps<{ decision: RoutingDecision, siuOpen?: boolean, compact?: boolean }>(), { siuOpen: false, compact: false })
const emit = defineEmits<{ seek: [seconds: number] }>()
const whyTitle = computed(() => {
  const r = props.decision.route
  if (r === 'fast_track') return 'Why fast-track'
  if (r === 'adjuster') return 'Why an adjuster, not fast-track'
  return 'Why a closer look'
})
const showSiu = computed(() => props.siuOpen && props.decision.route !== 'special_investigation')
const tone = computed(() => (props.decision.route === 'fast_track' ? 'fast' : props.decision.route === 'adjuster' ? 'adj' : 'siu'))
</script>

<template>
  <div class="unfurl" :class="{ compact }">
    <div class="routebig">
      <RouteTag :route="decision.route" :label="decision.routeLabel" lg class="ru" />
      <template v-if="showSiu">
        <span class="and">and</span>
        <RouteTag route="special_investigation" lg class="ru" />
      </template>
    </div>
    <slot name="note" />
    <h4 class="whyh">
      {{ whyTitle }}
    </h4>
    <ol class="why" :class="tone">
      <li v-for="(r, i) in decision.reasons" :key="r.feature" :style="{ animationDelay: `${300 + i * 90}ms` }">
        <span class="n num">{{ i + 1 }}</span>
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
.routebig { display: flex; align-items: center; gap: 12px; margin: 0 0 10px; flex-wrap: wrap; }
.routebig :deep(.ru) { animation: route-in var(--m-route) var(--ease-voice) both; }
.and { color: var(--cv-muted); font-weight: 650; font-size: 14px; }
.whyh { font-family: var(--font-sans); font-size: 13px; font-weight: 650; color: var(--cv-muted); margin: 14px 0 4px; }
.why { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--cv-rule); }
.why li {
  display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 9px 0;
  border-bottom: 1px solid var(--cv-rule); font-size: 15px; min-height: 46px; animation: rise-in 300ms var(--ease-voice) both;
}
.n {
  width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-weight: 720; font-size: 13px;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100;
}
.adj .n { background: var(--cv-adj-wash); color: var(--cv-adj); }
.fast .n { background: var(--cv-fast-wash); color: var(--cv-fast); }
.siu .n { background: var(--cv-siu-wash); color: var(--cv-siu); }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.rules { margin: 10px 0 0; font-size: 13px; color: var(--cv-muted); display: flex; gap: 6px; align-items: center; }
.compact .why li { font-size: 14px; min-height: 40px; padding: 7px 0; }
.compact .whyh { margin-top: 10px; }
:global(.reduce-motion) .routebig :deep(.ru), :global(.reduce-motion) .why li { animation: none; }
</style>
