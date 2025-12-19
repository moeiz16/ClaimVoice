<script setup lang="ts">
// Route reveal: the route tag unfurls (clip-path, 600 ms) and three plain reasons stagger in (90 ms), each with the
// moment it was heard. Reduced motion: appears complete.
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
    <div class="group-label">
      {{ whyTitle }}
    </div>
    <ol class="why" :class="decision.route === 'fast_track' ? 'fast' : decision.route === 'adjuster' ? 'adj' : 'siu'">
      <li v-for="(r, i) in decision.reasons" :key="r.feature" :style="{ animationDelay: `${300 + i * 90}ms` }">
        <span class="n">{{ i + 1 }}</span>
        <span>{{ r.text }}</span>
        <button v-if="r.atSeconds != null" class="heard chip" type="button" :aria-label="`Play from ${fmtClock(r.atSeconds)}`" @click="emit('seek', r.atSeconds!)">
          <span class="at"><CvIcon name="play" size="s" class="tri" />{{ fmtClock(r.atSeconds) }}</span>
        </button>
      </li>
    </ol>
    <p v-if="decision.rulesApplied.length" class="rules">
      <CvIcon name="check" size="s" />{{ decision.rulesApplied.join(' · ') }}
    </p>
  </div>
</template>

<style scoped>
.routebig { display: flex; align-items: center; gap: 12px; margin: 12px 0 8px; flex-wrap: wrap; }
.routebig :deep(.ru) { height: 40px; font-size: 16px; padding: 0 18px 0 14px; animation: route-in var(--m-route) var(--ease-voice) both; }
.and { color: var(--cv-muted); font-weight: 650; font-size: 14px; }
.why { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }
.why li { display: grid; grid-template-columns: 26px 1fr auto; gap: 8px; align-items: center; background: var(--cv-surface); border-radius: 14px; padding: 6px 8px 6px 10px; font-size: 14px; min-height: 40px; animation: rise-in 300ms var(--ease-voice) both; }
.n { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-weight: 800; font-size: 12px; }
.adj .n { background: var(--cv-adj-wash); color: var(--cv-adj); }
.fast .n { background: var(--cv-fast-wash); color: var(--cv-fast); }
.siu .n { background: var(--cv-siu-wash); color: var(--cv-siu); }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.rules { margin: 10px 0 0; font-size: 13px; color: var(--cv-muted); display: flex; gap: 6px; align-items: center; }
</style>
