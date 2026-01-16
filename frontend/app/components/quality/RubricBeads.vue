<script setup lang="ts">
// The six rubric beads: small pills with an icon, a word and ✓ or ✕, each saying met, missed or not applicable in
// words for screen readers (never colour alone). Not applicable reads as a dash.
import type { Bead } from '~/types/api'
import { beadIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'

withDefaults(defineProps<{ beads: Bead[], small?: boolean }>(), { small: false })
</script>

<template>
  <ul class="beads" :class="{ small }" aria-label="Call quality rubric">
    <li v-for="b in beads" :key="b.key" :class="b.passed === true ? 'ok' : b.passed === false ? 'miss' : 'na'">
      <UIcon :name="icon(beadIcon(b.key))" class="ic" />
      <span class="lb">{{ b.label }}<template v-if="b.detail"> ({{ b.detail }})</template></span>
      <UIcon v-if="b.passed === true" name="i-lucide-check" class="mk" />
      <UIcon v-else-if="b.passed === false" name="i-lucide-x" class="mk" />
      <UIcon v-else name="i-lucide-minus" class="mk" />
      <span class="sr-only-cv">{{ b.passed === true ? 'met' : b.passed === false ? 'missed' : 'not applicable' }}</span>
    </li>
  </ul>
</template>

<style scoped>
.beads { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 5px; }
li { display: inline-flex; align-items: center; gap: 5px; height: 30px; padding: 0 9px 0 10px; border-radius: 999px; font-size: 12.5px; font-weight: 500; white-space: nowrap; }
.ic, .mk { width: 14px; height: 14px; flex: none; }
.ok { background: var(--cv-fast-wash); color: var(--cv-fast); }
.miss { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
.na { background: var(--cv-sunk); color: var(--cv-muted); }
.small li { height: 26px; font-size: 11.5px; padding: 0 7px; gap: 4px; }
.small .ic, .small .mk { width: 12px; height: 12px; }
.small .lb { max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
</style>
