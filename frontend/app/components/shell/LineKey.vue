<script setup lang="ts">
// A line key in the key bank: the line's number, its lamp and a level bar. The lamp is a glyph with a word in the
// tooltip and accessible name, never colour alone: steady orchid = you're listening, a soft 1 Hz blink = waiting for
// a person, blink + red ring = urgent safety, cobalt = a person has it. Pressing a key opens that line's call.
import type { BoardRow } from '~/utils/board'
import { keyLabel, LAMP_GLYPH } from '~/utils/board'

// `plain` renders the key face only (inside the lit key's popover trigger, which is the button).
const props = withDefaults(defineProps<{ row: BoardRow, listening?: boolean, current?: boolean, row2?: boolean, plain?: boolean }>(), { listening: false, current: false, row2: false, plain: false })
const NuxtLink = resolveComponent('NuxtLink')
const clock = useDemoClock()
const waited = computed(() => clock.elapsed(props.row.since))
const label = computed(() => `${keyLabel(props.row, waited.value)}${props.listening ? ' · you are listening' : ''}`)
const waiting = computed(() => props.row.lamp === 'urgent' || props.row.lamp === 'waiting')
</script>

<template>
  <UTooltip :text="label" :content="{ side: row2 ? 'bottom' : 'left' }" :disabled="plain">
    <component
      :is="plain ? 'span' : NuxtLink" :to="plain ? undefined : `/lines/${row.callId}`" class="key" :class="[`lamp-${row.lamp}`, { listening, current }]"
      :aria-label="plain ? undefined : label" :aria-current="current && !plain ? 'page' : undefined"
    >
      <span class="n num">{{ row.lineNo ?? '·' }}</span>
      <span class="lamp" aria-hidden="true"><UIcon :name="listening ? 'i-lucide-headphones' : LAMP_GLYPH[row.lamp]" class="size-3" /></span>
      <span v-if="waiting" class="t num" aria-hidden="true">{{ waited }}</span>
      <span v-else-if="row.language === 'fr'" class="t" aria-hidden="true">FR</span>
    </component>
  </UTooltip>
</template>

<style scoped>
.key {
  position: relative; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; align-items: center;
  width: 64px; height: 50px; padding: 6px 7px 5px 9px; border-radius: 10px; text-decoration: none;
  background: var(--cv-dock-raise); color: var(--cv-on-dock); box-shadow: inset 0 -2px 0 rgba(0, 0, 0, .25);
  transition: transform 120ms var(--ease-voice), background-color 160ms;
}
.key:hover { background: color-mix(in srgb, var(--cv-dock-raise) 80%, white 8%); }
.key:active { transform: translateY(1px); box-shadow: none; }
.key:focus-visible { outline: 3px solid var(--cv-dock-orchid); outline-offset: 2px; }
.key.current { box-shadow: inset 0 0 0 2px var(--cv-on-dock); }
.n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 20px; line-height: 1; }
.lamp {
  width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center;
  background: color-mix(in srgb, var(--cv-on-dock) 18%, transparent); color: var(--cv-on-dock);
}
.t { grid-column: 1 / -1; font-size: 10.5px; font-weight: 650; color: var(--cv-dock-muted); line-height: 1.1; }
.lamp-line .lamp { background: color-mix(in srgb, var(--cv-dock-orchid) 30%, transparent); color: var(--cv-dock-orchid); }
.lamp-waiting .lamp { background: #F2C36B; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-urgent { box-shadow: inset 0 0 0 2px #FF8070; }
.lamp-urgent .lamp { background: #FF8070; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-urgent .t { color: #FFB3A8; }
.lamp-person .lamp { background: #8FAEFF; color: #1F2747; }
.key.listening { background: var(--cv-dock-orchid); color: #2A1530; }
.key.listening .lamp { background: #2A1530; color: var(--cv-dock-orchid); animation: none; }
.key.listening .t { color: #2A1530; }
:global(:root.reduce-motion) .lamp { animation: none !important; }
@media (prefers-reduced-motion: reduce) { .lamp { animation: none !important; } }
</style>
