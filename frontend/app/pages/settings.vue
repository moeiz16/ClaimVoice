<script setup lang="ts">
// Settings: the slate, then the section links as a ruled row of tabs, then the section itself as a full-width ruled
// document. Changes take effect for calls answered after the change; a live call keeps the script it started with.
// Every change is written to the activity log.
import type { NavigationMenuItem } from '@nuxt/ui'

useHead({ title: 'Settings · ClaimVoice' })
const { can } = useSession()
const sections: NavigationMenuItem[] = [
  { to: '/settings/scripts', label: 'Scripts', icon: 'i-lucide-message-square-more' },
  { to: '/settings/consent', label: 'Consent rules', icon: 'i-lucide-shield-check' },
  { to: '/settings/handoff', label: 'Hand-off rules', icon: 'i-lucide-user-round-plus' },
  { to: '/settings/languages', label: 'Languages', icon: 'i-lucide-languages' },
  { to: '/settings/retention', label: 'Retention', icon: 'i-lucide-clock' },
  { to: '/settings/privacy', label: 'Privacy', icon: 'i-lucide-lock' },
  { to: '/settings/people', label: 'People', icon: 'i-lucide-users-round' },
]
const manage = computed(() => can('settings:manage'))
</script>

<template>
  <div>
    <Slate title="Settings" :caption="`Larkspur Mutual · changes apply to calls answered after you save${manage ? '' : ' · you can view these; an administrator changes them'}`">
      <UButton v-if="can('audit:read')" to="/activity" color="neutral" variant="soft" icon="i-lucide-link-2" class="hide-phone">
        Activity log
      </UButton>
    </Slate>
    <nav class="sections" aria-label="Settings sections">
      <UNavigationMenu
        :items="sections" orientation="horizontal" variant="link" color="primary" highlight highlight-color="primary"
        :ui="{ root: 'justify-start', list: 'gap-1', link: 'text-[14.5px] font-semibold py-3 px-3 whitespace-nowrap', linkLeadingIcon: 'size-4' }"
      />
    </nav>
    <div class="body">
      <NuxtPage />
    </div>
  </div>
</template>

<style scoped>
.sections { padding: 0 20px; border-bottom: 1px solid var(--cv-rule); overflow-x: auto; scrollbar-width: none; }
@media (max-width: 720px) { .sections { padding: 0 4px; } }
</style>
