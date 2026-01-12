<script setup lang="ts">
// Where a claim goes, as a badge with its icon and word: ✓ Fast-track · Adjuster · Closer look.
import type { Route } from '~/types/api'
import { routeStyle } from '~/utils/labels'

const props = withDefaults(defineProps<{ route: Route | 'closer_look', label?: string | null, lg?: boolean }>(), { label: null, lg: false })
const s = computed(() => routeStyle(props.route))
</script>

<template>
  <CvTag :kind="s.kind" :icon="s.icon" :lg="lg">{{ label ?? s.label }}</CvTag>
</template>
