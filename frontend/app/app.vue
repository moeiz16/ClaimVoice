<script setup lang="ts">
// Theme, caption size and reduced motion are applied to <html> once, here. UApp provides Nuxt UI's toasts, tooltips
// and overlays to every page.
applyPrefs()
</script>

<template>
  <UApp :toaster="{ position: 'bottom-right', duration: 4200 }" :tooltip="{ delayDuration: 250 }">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
