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
.cv-logo { display: inline-flex; align-items: center; gap: 9px; text-decoration: none; color: var(--cv-ink); }
.cv-logo b {
  font-family: var(--font-display); font-weight: 750; font-size: 21px; letter-spacing: -0.035em;
  font-variation-settings: "opsz" 48, "wdth" 92;
}
.cv-logo b span { color: var(--cv-orchid); }
</style>
