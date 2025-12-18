<script setup lang="ts">
// The script track: seven stops (Consent → Policy → Safety → What happened → Photos → Coverage → Read-back). Done
// stops show ✓, the current stop is a raised pill with a live dot, future stops show their number. At the right,
// the safety watch, always visible.
import type { StageInfo } from '~/types/api'

const props = withDefaults(defineProps<{ stage: StageInfo, ended?: boolean, watch?: string[] }>(), { ended: false, watch: () => ['injury', 'gas', 'water near power', 'distress'] })
const STOPS = ['Consent', 'Policy', 'Safety', 'What happened', 'Photos', 'Coverage', 'Read-back']
const cur = computed(() => (props.ended ? STOPS.length + 1 : props.stage.step))
</script>

<template>
  <div class="script">
    <ol class="track" aria-label="Where the call is in the script">
      <li v-for="(s, i) in STOPS" :key="s" class="stop" :class="{ done: i + 1 < cur, cur: i + 1 === cur }" :aria-current="i + 1 === cur ? 'step' : undefined">
        <CvIcon v-if="i + 1 < cur" name="check" size="s" />
        <i v-else-if="i + 1 === cur" aria-hidden="true" />
        <span v-else class="n num">{{ i + 1 }}</span>
        <span class="l">{{ s }}</span>
        <span v-if="i + 1 < cur" class="sr-only-cv">, done</span>
      </li>
    </ol>
    <div v-if="!ended" class="watch">
      <CvIcon name="urgent" size="s" />Listening for <b>{{ watch.join(' · ') }}</b>
    </div>
  </div>
</template>

<style scoped>
.script { display: flex; align-items: center; gap: 18px; }
.track { flex: 1; display: flex; gap: 6px; background: var(--cv-sunk); padding: 5px; border-radius: 999px; list-style: none; margin: 0; min-width: 0; }
.stop { flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px; height: 36px; border-radius: 999px; font-size: 13.5px; font-weight: 650; color: var(--cv-muted); white-space: nowrap; }
.stop.done { color: var(--cv-ink); }
.stop.done :deep(svg) { color: var(--cv-fast); }
.stop.cur { background: var(--cv-surface); color: var(--cv-orchid-ink); box-shadow: var(--cv-shadow-pill); }
.stop.cur i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); animation: livedot 1.8s infinite; }
.n { width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; font-size: 11px; background: var(--cv-sunk-2); }
.watch { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--cv-muted); font-weight: 600; white-space: nowrap; }
.watch b { color: var(--cv-ink); }
@media (max-width: 1280px) { .watch { display: none; } }
@media (max-width: 720px) {
  .track { overflow-x: auto; scrollbar-width: none; }
  .stop { flex: none; padding: 0 12px; }
  .stop:not(.cur) .l { display: none; }
}
</style>
