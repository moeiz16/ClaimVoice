<script setup lang="ts">
// The six rubric beads: small pills with an icon, a word and ✓ or ✕. Not applicable reads as a dash.
import type { Bead } from '~/types/api'
import { beadIcon } from '~/utils/labels'

withDefaults(defineProps<{ beads: Bead[], small?: boolean }>(), { small: false })
</script>

<template>
  <ul class="beads" :class="{ small }" aria-label="Call quality rubric">
    <li v-for="b in beads" :key="b.key" :class="b.passed === true ? 'ok' : b.passed === false ? 'miss' : 'na'">
      <CvIcon :name="beadIcon(b.key)" size="s" />
      <span>{{ b.label }}<template v-if="b.detail"> ({{ b.detail }})</template></span>
      <CvIcon :name="b.passed === true ? 'check' : b.passed === false ? 'x' : 'dots'" size="s" class="mk" />
      <span class="sr-only-cv">{{ b.passed === true ? 'met' : b.passed === false ? 'missed' : 'not applicable' }}</span>
    </li>
  </ul>
</template>

<style scoped>
.beads { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 5px; }
li { display: inline-flex; align-items: center; gap: 5px; height: 28px; padding: 0 8px 0 9px; border-radius: 999px; font-size: 12.5px; font-weight: 650; white-space: nowrap; }
.ok { background: var(--cv-fast-wash); color: var(--cv-fast); }
.miss { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.na { background: var(--cv-sunk); color: var(--cv-muted); }
.small li { height: 24px; font-size: 11.5px; padding: 0 7px; }
.small li > span:not(.sr-only-cv) { max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
</style>
