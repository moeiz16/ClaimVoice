<script setup lang="ts">
withDefaults(defineProps<{ to?: string }>(), { to: '/' })
</script>

<template>
  <NuxtLink :to="to" class="cv-logo" aria-label="ClaimVoice home">
    <CvMark :size="30" />
    <b>Claim<span>Voice</span></b>
  </NuxtLink>
</template>

<style scoped>
.cv-logo { display: inline-flex; align-items: center; gap: 9px; text-decoration: none; color: var(--cv-ink); flex: none; }
/* The name is said, so it is set in the voice face: Commissioner, flared. */
.cv-logo b {
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 21px;
  letter-spacing: -0.025em; line-height: 1;
}
.cv-logo b span { color: var(--cv-orchid); }
</style>
