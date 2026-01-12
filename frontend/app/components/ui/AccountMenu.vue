<script setup lang="ts">
// The avatar key at the foot of the key bank and its menu (Nuxt UI DropdownMenu): who you are, Night line, caption
// size, Reduce motion, the activity log and sign out.
import type { DropdownMenuItem } from '@nuxt/ui'
import { initials } from '~/utils/format'

withDefaults(defineProps<{ side?: 'left' | 'bottom' | 'top' | 'right' }>(), { side: 'left' })
const { me, signOut, can } = useSession()
const prefs = usePrefs()

async function out() {
  await signOut()
  await navigateTo('/sign-in')
}

const items = computed<DropdownMenuItem[][]>(() => [
  [{ type: 'label', label: me.value?.user.fullName ?? '', description: `${me.value?.membership?.roleLabel ?? ''} · ${me.value?.activeOrg?.name ?? ''}` } as DropdownMenuItem],
  [
    { type: 'checkbox', label: 'Night line', icon: 'i-lucide-moon', checked: prefs.theme.value === 'dark', onUpdateChecked: (v: boolean) => { prefs.theme.value = v ? 'dark' : 'light' }, onSelect: (e: Event) => e.preventDefault() },
    { type: 'checkbox', label: 'Reduce motion', icon: 'i-lucide-pause', checked: prefs.reduceMotionSetting.value, onUpdateChecked: (v: boolean) => { prefs.reduceMotionSetting.value = v }, onSelect: (e: Event) => e.preventDefault() },
  ],
  [
    { type: 'label', label: 'Caption size' },
    ...(['s', 'm', 'l'] as const).map(s => ({
      type: 'checkbox' as const, label: { s: 'Small', m: 'Medium', l: 'Large' }[s], checked: prefs.captions.value === s,
      onUpdateChecked: () => { prefs.captions.value = s }, onSelect: (e: Event) => e.preventDefault(),
    })),
  ],
  [
    ...(can('audit:read') ? [{ label: 'Activity log', icon: 'i-lucide-link-2', to: '/activity' }] : []),
    { label: 'Sign out', icon: 'i-lucide-log-out', onSelect: () => { void out() } },
  ],
])
</script>

<template>
  <UDropdownMenu v-if="me" :items="items" :content="{ side, align: 'end', sideOffset: 10 }" :ui="{ content: 'w-64' }">
    <button class="acct" type="button" :aria-label="`${me.user.fullName}, ${me.membership?.roleLabel ?? ''}: account menu`">
      <UAvatar :text="initials(me.user.fullName)" size="md" class="bg-person-wash text-person font-bold" />
    </button>
  </UDropdownMenu>
</template>

<style scoped>
.acct { border: 0; background: none; padding: 2px; border-radius: 999px; display: grid; place-items: center; }
.acct:focus-visible { outline-color: var(--cv-dock-orchid); }
</style>
