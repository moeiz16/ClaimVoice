<template>
  <div class="public">
    <slot />
  </div>
</template>

<style scoped>
/* Public pages (landing, sign in, demo line, photo link): no key bank; full-bleed bands, never a sideways scroll. */
.public { min-height: 100dvh; background: var(--cv-bg); color: var(--cv-ink); overflow-x: clip; }
</style>
