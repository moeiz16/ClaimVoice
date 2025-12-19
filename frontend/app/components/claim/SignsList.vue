<script setup lang="ts">
// Signs worth a closer look, each with its moment or its source, and the shield note: a sign is never a reason to
// deny a claim on its own.
import type { SiuIndicator } from '~/types/api'
import { fmtClock } from '~/utils/format'

defineProps<{ signs: SiuIndicator[], checked: number, statement: string }>()
const emit = defineEmits<{ seek: [seconds: number] }>()
</script>

<template>
  <div class="signs">
    <div class="group-label">
      Signs worth a closer look · {{ signs.length }} of the {{ checked }} we check
    </div>
    <ol class="why">
      <li v-for="(s, i) in signs" :key="s.key">
        <span class="n">{{ i + 1 }}</span>
        <span>{{ s.label }}<small v-if="s.evidence && s.evidence !== s.label">{{ s.evidence }}</small></span>
        <button v-if="s.atSeconds != null" class="heard chip" type="button" :aria-label="`Play from ${fmtClock(s.atSeconds)}`" @click="emit('seek', s.atSeconds!)">
          <span class="at"><CvIcon name="play" size="s" class="tri" />{{ fmtClock(s.atSeconds) }}</span>
        </button>
        <span v-else class="src">{{ s.sourceLabel }}</span>
      </li>
    </ol>
    <p class="never">
      <CvIcon name="shield" size="s" />{{ statement }}
    </p>
  </div>
</template>

<style scoped>
.signs { margin-top: 16px; }
.why { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }
.why li { display: grid; grid-template-columns: 26px 1fr auto; gap: 8px; align-items: center; background: var(--cv-surface); border-radius: 14px; padding: 6px 8px 6px 10px; font-size: 14px; }
.why small { display: block; color: var(--cv-muted); font-size: 12.5px; }
.n { width: 24px; height: 24px; border-radius: 50%; background: var(--cv-siu-wash); color: var(--cv-siu); display: grid; place-items: center; font-weight: 800; font-size: 12px; }
.src { font-size: 12px; color: var(--cv-muted); font-weight: 600; white-space: nowrap; }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.never { display: flex; gap: 8px; align-items: flex-start; margin: 10px 0 0; padding: 10px 12px; border-radius: 14px; background: var(--cv-surface); font-size: 13.5px; font-weight: 600; }
.never :deep(svg) { color: var(--cv-siu); margin-top: 2px; }
</style>
