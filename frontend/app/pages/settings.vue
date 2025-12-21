<script setup lang="ts">
// Settings: sections as pills under the header. Changes take effect for calls answered after the change; a live
// call keeps the script it started with. Every change is written to the activity log.
useHead({ title: 'Settings · ClaimVoice' })
const route = useRoute()
const { can } = useSession()
const sections = [
  { to: '/settings/scripts', label: 'Scripts', icon: 'whisper' },
  { to: '/settings/consent', label: 'Consent rules', icon: 'shield' },
  { to: '/settings/handoff', label: 'Hand-off rules', icon: 'handoff' },
  { to: '/settings/languages', label: 'Languages', icon: 'lang' },
  { to: '/settings/retention', label: 'Retention', icon: 'clock' },
  { to: '/settings/privacy', label: 'Privacy', icon: 'lock' },
  { to: '/settings/people', label: 'People', icon: 'people' },
]
const manage = computed(() => can('settings:manage'))
</script>

<template>
  <div>
    <PageHeader title="Settings" :caption="`Larkspur Mutual · changes apply to calls answered after you save${manage ? '' : ' · you can view these; an administrator changes them'}`">
      <NuxtLink v-if="can('audit:read')" class="btn soft sm hide-phone" to="/activity">
        <CvIcon name="chain" size="s" />Activity log
      </NuxtLink>
    </PageHeader>
    <nav class="pills" aria-label="Settings sections">
      <NuxtLink v-for="s in sections" :key="s.to" :to="s.to" class="pill" :aria-current="route.path === s.to ? 'page' : undefined">
        <CvIcon :name="s.icon" size="s" />{{ s.label }}
      </NuxtLink>
    </nav>
    <div class="body">
      <NuxtPage />
    </div>
  </div>
</template>

<style scoped>
.pills { display: flex; gap: 6px; margin: 0 32px 16px; overflow-x: auto; scrollbar-width: none; padding: 2px; }
.pill { display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 14px; border-radius: 999px; background: var(--cv-sunk); font-weight: 650; font-size: 14px; color: var(--cv-muted); text-decoration: none; white-space: nowrap; flex: none; }
.pill:hover { color: var(--cv-ink); }
.pill[aria-current="page"] { background: var(--cv-ink); color: var(--cv-bg); }
.body { margin: 0 32px; }
@media (max-width: 720px) { .pills, .body { margin-left: 16px; margin-right: 16px; } }
</style>
