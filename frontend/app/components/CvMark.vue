<script setup lang="ts">
// The mark: a rounded orchid speech tile with a tail at the lower left; five bars rise into a tick (voice → filed).
withDefaults(defineProps<{ size?: number }>(), { size: 30 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true" focusable="false" style="flex: none">
    <path
      d="M11 2.5h10a8.5 8.5 0 0 1 8.5 8.5v6.6a8.5 8.5 0 0 1-8.5 8.5h-8.3l-5.6 3.8a.7.7 0 0 1-1.1-.7l.9-4.9A8.5 8.5 0 0 1 2.5 17.6V11A8.5 8.5 0 0 1 11 2.5z"
      fill="var(--cv-orchid)"
    />
    <g stroke="#fff" stroke-width="2.5" stroke-linecap="round">
      <path d="M9 13.4v2.4" /><path d="M13 14.4v5.2" /><path d="M17.2 10.4v8.2" /><path d="M21.4 7.6v6.2" /><path d="M25.2 7.6v1.8" opacity=".75" />
    </g>
  </svg>
</template>
