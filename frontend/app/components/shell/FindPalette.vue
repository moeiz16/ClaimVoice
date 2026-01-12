<script setup lang="ts">
// Find: a command palette (Nuxt UI CommandPalette in a Modal) over the lines on the board, this morning's claims and
// the pages you can open. Opened from the key bank's Find key, or with / and ⌘K.
import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui'
import { boardRows } from '~/utils/board'
import { navFor } from '~/composables/useSession'

const open = defineModel<boolean>('open', { default: false })
const { permissions, can } = useSession()
const { snapshot } = useSwitchboard(false)
const term = ref('')
const nav = computed(() => navFor(permissions.value))

const groups = computed<CommandPaletteGroup<CommandPaletteItem>[]>(() => {
  const pages: CommandPaletteItem[] = [
    nav.value.lines && { id: 'p-lines', label: 'The board', suffix: 'Lines', icon: 'i-lucide-list-checks', to: '/lines', kbds: ['G', 'L'] },
    nav.value.claims && { id: 'p-claims', label: 'Claims', icon: 'i-lucide-file-text', to: '/claims', kbds: ['G', 'C'] },
    nav.value.quality && { id: 'p-quality', label: 'Call quality', icon: 'i-lucide-flag', to: '/quality', kbds: ['G', 'Q'] },
    nav.value.routing && { id: 'p-routing', label: 'Routing checks', icon: 'i-lucide-scale', to: '/routing', kbds: ['G', 'R'] },
    nav.value.settings && { id: 'p-settings', label: 'Settings', icon: 'i-lucide-sliders-horizontal', to: '/settings', kbds: ['G', 'S'] },
    can('audit:read') && { id: 'p-activity', label: 'Activity log', icon: 'i-lucide-link-2', to: '/activity' },
  ].filter(Boolean) as CommandPaletteItem[]
  const rows = snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []
  const lines: CommandPaletteItem[] = rows.map(r => ({ id: `l-${r.callId}`, label: `${r.lineLabel} · ${r.callerLabel}`, suffix: [r.stateWord, r.place].filter(Boolean).join(' · '), icon: 'i-lucide-audio-lines', to: `/lines/${r.callId}` }))
  const claims: CommandPaletteItem[] = (snapshot.value?.recentClaims ?? []).map(c => ({ id: `c-${c.id}`, label: `${c.claimNumber} · ${c.holderName}`, suffix: c.lossPlace ?? c.regionLabel, icon: 'i-lucide-file-text', to: `/claims/${c.id}` }))
  const out: CommandPaletteGroup<CommandPaletteItem>[] = []
  if (lines.length) out.push({ id: 'lines', label: 'On the lines', items: lines })
  if (claims.length) out.push({ id: 'claims', label: 'Claims this morning', items: claims })
  if (can('claims:read') && term.value.trim().length > 1) {
    out.push({ id: 'search', label: 'Search', ignoreFilter: true, items: [{ id: 's', label: `Find claims matching “${term.value.trim()}”`, icon: 'i-lucide-search', to: `/claims?q=${encodeURIComponent(term.value.trim())}` }] })
  }
  out.push({ id: 'pages', label: 'Go to', items: pages })
  return out
})

function onSelect() { open.value = false; term.value = '' }
</script>

<template>
  <UModal v-model:open="open" title="Find" description="Lines, claims and pages" :ui="{ content: 'max-w-xl' }">
    <template #content>
      <UCommandPalette
        v-model:search-term="term" :groups="groups" placeholder="Find a line, a claim or a page…" close
        :ui="{ input: '[&_input]:text-[16px]' }" class="h-[min(460px,70dvh)]"
        @update:model-value="onSelect" @update:open="(v: boolean) => { if (!v) open = false }"
      />
    </template>
  </UModal>
</template>
