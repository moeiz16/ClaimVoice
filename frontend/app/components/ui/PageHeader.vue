<script setup lang="ts">
// The top of every app page: a large title, a one-line context caption, and only page-level controls at the right.
withDefaults(defineProps<{ title: string, caption?: string | null, back?: { to: string, label: string } | null }>(), { caption: null, back: null })
</script>

<template>
  <header class="top">
    <NuxtLink v-if="back" :to="back.to" class="back"><CvIcon name="left" size="s" />{{ back.label }}</NuxtLink>
    <div class="ctx">
      <h1>{{ title }}</h1>
      <span v-if="caption || $slots.caption" class="sub"><slot name="caption">{{ caption }}</slot></span>
    </div>
    <div class="right">
      <slot />
      <AccountMenu />
    </div>
  </header>
</template>

<style scoped>
.top { display: flex; align-items: center; gap: 18px; min-height: 72px; padding: 0 32px; }
.back { display: inline-flex; align-items: center; gap: 4px; font-weight: 650; color: var(--cv-muted); text-decoration: none; font-size: 14px; margin-right: 6px; white-space: nowrap; }
.back:hover { color: var(--cv-ink); }
.ctx { display: flex; align-items: baseline; gap: 14px; min-width: 0; }
h1 { font-size: 30px; font-weight: 750; letter-spacing: -0.03em; white-space: nowrap; }
.sub { color: var(--cv-muted); font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
@media (max-width: 1100px) { .sub { white-space: normal; } }
@media (max-width: 720px) {
  .top { min-height: 60px; padding: 0 16px; gap: 10px; }
  h1 { font-size: 24px; overflow: hidden; text-overflow: ellipsis; }
  .sub { display: none; }
  .right :deep(.hide-phone) { display: none; }
}
</style>
