<script setup lang="ts">
// Signs worth a closer look, folded (Nuxt UI Accordion): each sign with its moment (a ▸ chip that plays the tape) or
// its source ("from the policy", "claim history"), then the shield note: a sign is never a reason to deny a claim on
// its own. `open` is a v-model so the page can open it from ?signs.
import type { SiuIndicator } from '~/types/api'
import { fmtClock } from '~/utils/format'

const NEVER_DENY = 'For a person to review. A sign is never a reason to deny a claim on its own, and nothing here was decided automatically.'
const props = defineProps<{ signs: SiuIndicator[], checked: number, statement: string }>()
const emit = defineEmits<{ seek: [seconds: number] }>()
const open = defineModel<boolean>('open', { default: false })
const value = computed({ get: () => (open.value ? 'signs' : undefined), set: (v: string | undefined) => { open.value = v === 'signs' } })
const items = computed(() => [{ value: 'signs', label: `Signs worth a closer look · ${props.signs.length} of the ${props.checked} we check`, icon: 'i-lucide-search', slot: 'signs' as const }])
</script>

<template>
  <div class="signs">
    <UAccordion
      v-model="value" :items="items" :unmount-on-hide="false"
      :ui="{ trigger: 'py-3 text-[15px] font-semibold', leadingIcon: 'text-siu size-5', item: 'border-0' }"
    >
      <template #signs-body>
        <ol class="list">
          <li v-for="(s, i) in signs" :key="s.key">
            <span class="n num">{{ i + 1 }}</span>
            <span class="txt">{{ s.label }}<small v-if="s.evidence && s.evidence !== s.label">{{ s.evidence }}</small></span>
            <button v-if="s.atSeconds != null" class="heard chip" type="button" :aria-label="`Play from ${fmtClock(s.atSeconds)}`" @click="emit('seek', s.atSeconds!)">
              <span class="at"><UIcon name="i-lucide-play" class="tri" />{{ fmtClock(s.atSeconds) }}</span>
            </button>
            <span v-else class="src">{{ s.sourceLabel }}</span>
          </li>
        </ol>
        <p class="never">
          <UIcon name="i-lucide-shield-check" class="size-4 shield" />{{ statement || NEVER_DENY }}
        </p>
      </template>
    </UAccordion>
  </div>
</template>

<style scoped>
.signs { border-top: 1px solid var(--cv-rule); border-bottom: 1px solid var(--cv-rule); }
.list { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--cv-rule); }
.list li { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--cv-rule); font-size: 14.5px; }
.txt small { display: block; color: var(--cv-muted); font-size: 13px; }
.n { width: 26px; height: 26px; border-radius: 50%; background: var(--cv-siu-wash); color: var(--cv-siu); display: grid; place-items: center; font-weight: 720; font-size: 13px; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; }
.src { font-size: 12.5px; color: var(--cv-muted); font-weight: 600; white-space: nowrap; }
.chip { min-height: 0; padding: 3px; }
.chip .at { height: 22px; }
.chip :deep(.tri) { width: 11px; height: 11px; }
.never { display: flex; gap: 8px; align-items: flex-start; margin: 12px 0 4px; padding: 10px 12px; border-radius: 6px; background: var(--cv-siu-wash); font-size: 14px; font-weight: 600; color: var(--cv-ink); }
.never .shield { color: var(--cv-siu); margin-top: 2px; flex: none; }
</style>
