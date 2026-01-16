<script setup lang="ts">
withDefaults(defineProps<{ to?: string, size?: number }>(), { to: '/', size: 34 })
</script>

<template>
  <NuxtLink :to="to" class="cv-logo" aria-label="ClaimVoice home">
    <CvMark :size="size" />
    <b>ClaimVoice</b>
  </NuxtLink>
</template>

<style scoped>
.cv-logo { display: inline-flex; align-items: center; gap: 9px; text-decoration: none; color: var(--cv-ink); flex: none; border-radius: 14px; }
/* The name is said, so it is set in the heading face: Nunito Black. */
.cv-logo b { font-family: var(--font-round); font-weight: 900; font-size: 22px; letter-spacing: -0.02em; line-height: 1; }
</style>
