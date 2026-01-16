<script setup lang="ts">
// Change route: a dialog with the three routes as cards (each an icon and a word, never colour alone), a required
// reason (free text or a common reason), and who is told. The change is written to the activity log.
import type { Route, RoutingDecision } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const props = defineProps<{ open: boolean, claimId: string, current: Route, claimNumber: string }>()
const emit = defineEmits<{ close: [], changed: [d: RoutingDecision] }>()
const route = ref<Route>(props.current)
const reason = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
watch(() => props.open, (o) => { if (o) { route.value = props.current; reason.value = ''; error.value = null } })
const isOpen = computed({ get: () => props.open, set: (v: boolean) => { if (!v) emit('close') } })

const options = [
  { value: 'fast_track' as const, label: 'Fast-track', description: 'Paid quickly from the photos; no visit', class: 'k-fast' },
  { value: 'adjuster' as const, label: 'Adjuster', description: 'An adjuster calls and works the claim', class: 'k-adj' },
  { value: 'special_investigation' as const, label: 'Closer look', description: 'Special investigations looks first. Never a denial.', class: 'k-siu' },
]
const common = ['Police report confirms the details', 'Damage is larger than it sounded', 'Caller needs a person', 'Photos show minor damage only']
const notify = computed(() => (route.value === 'special_investigation' ? 'Dev Malhotra in special investigations and the assigned adjuster are told.' : route.value === 'adjuster' ? 'The adjusters\' queue and the caller\'s next-steps text are updated.' : 'The caller gets a fast-track text with the photo link.'))

async function save() {
  if (!reason.value.trim()) { error.value = 'Give a reason for the change.'; return }
  busy.value = true
  error.value = null
  try {
    emit('changed', await api.claims.overrideRoute(props.claimId, route.value, reason.value.trim()))
    emit('close')
  }
  catch (e) { error.value = e instanceof ApiError ? (e.fieldError('reason') ?? e.message) : 'That didn\'t save. Try again.' }
  busy.value = false
}
</script>

<template>
  <UModal v-model:open="isOpen" :title="`Change the route of ${claimNumber}`" description="Pick where the claim goes and say why. The change is logged with your name." :ui="{ content: 'sm:max-w-xl' }">
    <template #body>
      <form id="change-route" class="grid gap-4" @submit.prevent="save">
        <URadioGroup v-model="route" :items="options" variant="card" color="neutral" legend="Route" class="routes" :ui="{ fieldset: 'grid gap-2', legend: 'sr-only-cv' }">
          <template #label="{ item }">
            <span class="rl">
              <UIcon v-if="item.value === 'fast_track'" name="i-lucide-check" class="size-5 text-fast" />
              <UIcon v-else-if="item.value === 'adjuster'" name="i-lucide-user-round" class="size-5 text-adj" />
              <UIcon v-else name="i-lucide-search" class="size-5 text-siu" />
              {{ item.label }}
              <small v-if="item.value === current" class="now">Now</small>
            </span>
          </template>
        </URadioGroup>

        <UFormField label="Reason" required :error="error ?? undefined" help="Up to 280 characters.">
          <UTextarea v-model="reason" autofocus :maxlength="280" :rows="3" autoresize class="w-full" placeholder="Police report confirms the SUV." />
        </UFormField>
        <div class="quick" role="group" aria-label="Common reasons">
          <UButton v-for="q in common" :key="q" size="sm" color="neutral" variant="soft" @click="reason = q; error = null">
            {{ q }}
          </UButton>
        </div>
        <p class="notify">
          <UIcon name="i-lucide-user-round" class="size-4" />{{ notify }} The change is logged with your name.
        </p>
      </form>
    </template>
    <template #footer>
      <div class="flex gap-2 flex-wrap">
        <UButton :loading="busy" :disabled="busy || route === current && !reason.trim()" @click="save">
          Change the route
        </UButton>
        <UButton color="neutral" variant="soft" @click="emit('close')">
          Keep it
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.rl { display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-round); font-size: 18px; font-weight: 850; }
.now { font-family: var(--font-sans); font-size: 12px; font-weight: 500; color: var(--cv-muted); padding: 1px 8px; border-radius: 999px; background: var(--cv-sunk); }
.routes :deep(.k-fast:has([data-state="checked"])) { background: var(--cv-fast-wash); box-shadow: inset 0 0 0 2px var(--cv-fast); border-color: transparent; }
.routes :deep(.k-adj:has([data-state="checked"])) { background: var(--cv-adj-wash); box-shadow: inset 0 0 0 2px var(--cv-adj); border-color: transparent; }
.routes :deep(.k-siu:has([data-state="checked"])) { background: var(--cv-siu-wash); box-shadow: inset 0 0 0 2px var(--cv-siu); border-color: transparent; }
.routes :deep(label) { cursor: pointer; border-radius: 20px; }
.quick { display: flex; flex-wrap: wrap; gap: 6px; margin-top: -6px; }
.notify { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-size: 13.5px; margin: 0; }
</style>
