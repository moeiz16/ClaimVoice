<script setup lang="ts">
// A status tag: always an icon and a word (status is never shown by colour alone).
withDefaults(defineProps<{ kind?: 'fast' | 'adj' | 'siu' | 'urgent' | 'orchid' | 'person' | 'plain', icon?: string, lg?: boolean }>(), { kind: 'plain', icon: undefined, lg: false })
</script>

<template>
  <span class="tag" :class="[kind, { lg }]"><CvIcon v-if="icon" :name="icon" size="s" /><slot /></span>
</template>
