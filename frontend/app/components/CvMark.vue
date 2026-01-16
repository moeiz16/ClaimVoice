<script setup lang="ts">
// The mark: two voices in conversation. A jade pebble (ClaimVoice) with its tail at the lower left, overlapping a
// smaller sea-glass pebble (the caller) at the upper right. Round, soft, no hard corners.
withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 40 40" aria-hidden="true" focusable="false" style="flex: none">
    <circle cx="27.5" cy="13" r="10.5" fill="var(--cv-seaglass)" />
    <path d="M17 7.5c7.7 0 14 5.6 14 12.6s-6.3 12.6-14 12.6c-1.6 0-3.2-.2-4.6-.7l-5.3 3.2c-1 .6-2.2-.3-1.9-1.4l1.3-4.6C4.3 26.8 3 23.6 3 20.1 3 13.1 9.3 7.5 17 7.5Z" fill="var(--cv-jade)" />
    <circle cx="11.6" cy="20.2" r="2" fill="var(--cv-on-jade)" />
    <circle cx="17.2" cy="20.2" r="2" fill="var(--cv-on-jade)" />
    <circle cx="22.8" cy="20.2" r="2" fill="var(--cv-on-jade)" />
  </svg>
</template>
