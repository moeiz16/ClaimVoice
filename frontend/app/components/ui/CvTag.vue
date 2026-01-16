<script setup lang="ts">
// A status tag on Nuxt UI's Badge: always an icon and a word (status is never shown by colour alone). The kinds are
// ClaimVoice's statuses; each maps to a semantic colour whose soft variant is the AA-checked wash + ink pair.
import { icon as iconFor } from '~/utils/icons'

type Kind = 'fast' | 'adj' | 'siu' | 'urgent' | 'jade' | 'person' | 'plain' | 'caller'
const props = withDefaults(defineProps<{ kind?: Kind, icon?: string, lg?: boolean, variant?: 'soft' | 'subtle' | 'outline' | 'solid' }>(), { kind: 'plain', icon: undefined, lg: false, variant: 'soft' })
const COLOR = { fast: 'success', adj: 'info', person: 'info', siu: 'warning', urgent: 'error', jade: 'primary', plain: 'neutral', caller: 'secondary' } as const
const color = computed(() => COLOR[props.kind])
const leading = computed(() => (props.icon ? (props.icon.startsWith('i-') ? props.icon : iconFor(props.icon)) : undefined))
</script>

<template>
  <UBadge :color="color" :variant="variant" :size="lg ? 'xl' : 'lg'" :icon="leading" class="cv-tag" :class="`k-${kind}`">
    <slot />
  </UBadge>
</template>
