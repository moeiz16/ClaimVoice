<script setup lang="ts">
// Seven segments: done in orchid, the current one half-filled, the rest waiting. The words travel next to it.
import type { StageInfo } from '~/types/api'

defineProps<{ stage: StageInfo }>()
</script>

<template>
  <div class="steps" role="img" :aria-label="`Step ${stage.step} of ${stage.steps}: ${stage.stepLabel}`">
    <i v-for="n in stage.steps" :key="n" :class="{ done: n < stage.step, cur: n === stage.step }" />
  </div>
</template>

<style scoped>
.steps { display: flex; gap: 4px; }
.steps i { flex: 1; height: 6px; border-radius: 3px; background: var(--cv-sunk-2); }
.steps i.done { background: var(--cv-orchid); }
.steps i.cur { background: linear-gradient(90deg, var(--cv-orchid) 50%, var(--cv-sunk-2) 50%); }
</style>
