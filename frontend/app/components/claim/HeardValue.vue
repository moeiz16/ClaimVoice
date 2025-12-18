<script setup lang="ts">
// A claim-file value. Heard values are pills linked to the words they came from (▸ 1:52); values from the policy or
// a look-up say so; values not heard yet are dashed pills. Never a value without its source.
import type { Slot } from '~/types/api'
import { fmtClock } from '~/utils/format'

const props = withDefaults(defineProps<{ field: Slot, linked?: boolean, lang?: string }>(), { linked: false, lang: undefined })
const emit = defineEmits<{ activate: [], hover: [on: boolean] }>()
const heard = computed(() => props.field.source === 'heard' && !!props.field.display)
const chip = computed(() => props.field.sourceLabel.replace(/^▸\s*/, ''))
const unsure = computed(() => props.field.confidenceLabel === 'check')
const label = computed(() => {
  if (!heard.value) return `${props.field.label}: ${props.field.display}, ${props.field.sourceLabel}`
  return `${props.field.label}: ${props.field.display}. Heard at ${chip.value}. Show where.`
})
</script>

<template>
  <span class="hv">
    <button
      v-if="heard" type="button" class="heard" :class="{ linked, settling: unsure }" :lang="lang" :aria-label="label"
      @click="emit('activate')" @mouseenter="emit('hover', true)" @mouseleave="emit('hover', false)" @focus="emit('hover', true)" @blur="emit('hover', false)"
    >
      {{ field.display }}
      <span class="at">
        <template v-if="unsure">not sure yet</template>
        <template v-else><CvIcon name="play" size="s" class="tri" />{{ chip }}</template>
      </span>
    </button>
    <span v-else-if="field.display" class="src" :lang="lang">{{ field.display }} <small>{{ field.sourceLabel }}</small></span>
    <span v-else class="pending">{{ field.sourceLabel && !field.sourceLabel.startsWith('▸') ? field.sourceLabel : 'Not heard yet' }}</span>
    <span v-if="field.changedAtSeconds != null" class="tag siu"><CvIcon name="look" size="s" />Changed at {{ fmtClock(field.changedAtSeconds) }}</span>
  </span>
</template>

<style scoped>
.hv { display: contents; }
.heard { cursor: pointer; }
.heard :deep(.tri) { width: 11px; height: 11px; }
.src { font-size: 13.5px; font-weight: 600; display: inline-flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
.src small { color: var(--cv-muted); font-weight: 550; font-size: 12px; }
</style>
