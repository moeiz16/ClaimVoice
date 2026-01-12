<script setup lang="ts">
// The slate: the top of each page in the work area. A caption block, not a bar: an optional back link, the title in
// the line's voice (Commissioner, flared), one context line, and page-level controls. Left-aligned, ruled beneath.
// No navigation, no search and no avatar here: those live in the key bank.
withDefaults(defineProps<{ title: string, caption?: string | null, back?: { to: string, label: string } | null, eyebrow?: string | null }>(), { caption: null, back: null, eyebrow: null })
</script>

<template>
  <header class="slate">
    <div class="ctx">
      <div v-if="back || eyebrow || $slots.eyebrow" class="eyebrow">
        <NuxtLink v-if="back" :to="back.to" class="back"><UIcon name="i-lucide-arrow-left" class="size-4" />{{ back.label }}</NuxtLink>
        <span v-if="eyebrow">{{ eyebrow }}</span>
        <slot name="eyebrow" />
      </div>
      <h1>{{ title }}<slot name="title-after" /></h1>
      <p v-if="caption || $slots.caption" class="sub">
        <slot name="caption">{{ caption }}</slot>
      </p>
    </div>
    <div v-if="$slots.default" class="ctl">
      <slot />
    </div>
  </header>
</template>

<style scoped>
.slate { display: flex; align-items: flex-end; gap: 16px 24px; flex-wrap: wrap; padding: 22px 32px 16px; border-bottom: 1px solid var(--cv-rule); }
.ctx { min-width: 0; flex: 1 1 420px; }
.eyebrow { display: flex; align-items: center; gap: 14px; font-size: 13px; font-weight: 600; color: var(--cv-muted); margin-bottom: 4px; }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--cv-muted); text-decoration: none; }
.back:hover { color: var(--cv-ink); }
h1 { font-size: 34px; line-height: 1.08; font-weight: 720; letter-spacing: -0.02em; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sub { margin: 6px 0 0; color: var(--cv-muted); font-size: 14.5px; }
.ctl { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
@media (max-width: 720px) {
  .slate { padding: 14px 16px 12px; gap: 10px; }
  h1 { font-size: 26px; }
  .sub { font-size: 13.5px; }
  .ctl :deep(.hide-phone) { display: none; }
}
</style>
