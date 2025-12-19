<script setup lang="ts">
// One call's quality review on its own page (a shareable link; the queue opens the same review beside it).
const route = useRoute()
const id = computed(() => String(route.params.callId))
useHead({ title: 'Quality review · ClaimVoice' })
</script>

<template>
  <div>
    <PageHeader title="Quality review" :back="{ to: '/quality', label: 'Quality' }" />
    <div class="wrap">
      <ReviewPanel :key="id" :call-id="id" @done="navigateTo('/quality')" />
    </div>
  </div>
</template>

<style scoped>
.wrap { margin: 0 32px; max-width: 1100px; }
@media (max-width: 720px) { .wrap { margin: 0 16px; } }
</style>
