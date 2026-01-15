<script setup lang="ts">
// The surge band (Nuxt UI Alert, amber): what's happening in words, and the supervisor's two levers. "What's
// covered" opens the storm guidance in a popover.
import type { Surge } from '~/types/api'
import { api } from '~/utils/api'

const props = defineProps<{ surge: Surge, queueWords?: string | null }>()
const emit = defineEmits<{ updated: [s: Surge] }>()
const { can } = useSession()
const listening = useListening()
const busy = ref(false)
const kindIcon = computed(() => (props.surge.kind === 'hail' ? 'i-lucide-cloud-hail' : props.surge.kind === 'flood' || props.surge.kind === 'rainfall' ? 'i-lucide-droplet' : 'i-lucide-wind'))
const waitWords = computed(() => {
  const s = props.surge.waitForPersonSeconds
  return s < 60 ? 'under a minute' : s < 90 ? 'about 1 min' : `about ${Math.round(s / 60)} min`
})
const questionsWord = computed(() => `${props.surge.kindLabel} questions switched ${props.surge.surgeQuestionsOn ? 'on' : 'off'}`)

async function standby() {
  busy.value = true
  try {
    emit('updated', await api.switchboard.standby(props.surge.id))
    listening.flash('The standby team is on its way to the lines.')
  }
  catch { listening.flash('We couldn\'t reach the standby team. Try again.') }
  busy.value = false
}
async function toggleQuestions() {
  try { emit('updated', await api.switchboard.surgeQuestions(props.surge.id, !props.surge.surgeQuestionsOn)) }
  catch { listening.flash('That didn\'t change. Try again.') }
}
</script>

<template>
  <UAlert color="warning" variant="soft" :icon="kindIcon" class="surge" role="status" :ui="{ root: 'rounded-none px-8 py-3 max-[720px]:px-4 items-center', icon: 'size-6', title: 'font-voice text-[19px] [font-variation-settings:\'FLAR\'_100] text-ink', description: 'text-ink', actions: 'items-center' }">
    <template #title>
      {{ surge.title }} <span class="headline">· {{ surge.headline }}</span>
    </template>
    <template #description>
      <span class="facts">
        <span v-if="queueWords">{{ queueWords }}</span>
        <span v-else>Calls are <strong class="num">{{ surge.multiplier.toFixed(1) }}×</strong> usual {{ surge.sinceLabel }}</span>
        <USwitch v-if="can('lines:manage')" :model-value="surge.surgeQuestionsOn" :label="questionsWord" size="sm" color="warning" @update:model-value="toggleQuestions" />
        <span v-else><UIcon :name="surge.surgeQuestionsOn ? 'i-lucide-check' : 'i-lucide-x'" class="size-4" />{{ questionsWord }}</span>
        <span><UIcon name="i-lucide-clock" class="size-4" />Wait for a person: {{ waitWords }}</span>
      </span>
    </template>
    <template #actions>
      <UButton v-if="can('lines:manage') && !surge.standbyCalled" icon="i-lucide-users-round" :loading="busy" @click="standby">
        Bring in the standby team ({{ surge.standbyAvailable }})
      </UButton>
      <CvTag v-else-if="surge.standbyCalled" kind="fast" icon="check">Standby team on the lines</CvTag>
      <UPopover :content="{ side: 'bottom', align: 'end' }">
        <UButton color="neutral" variant="outline" class="bg-surface">
          What's covered
        </UButton>
        <template #content>
          <div class="guide">
            <UIcon name="i-lucide-shield-check" class="size-5 text-fast shrink-0" />
            <div>
              <p>{{ surge.guidance }}</p>
              <small>{{ surge.source }}</small>
            </div>
          </div>
        </template>
      </UPopover>
    </template>
  </UAlert>
</template>

<style scoped>
.headline { color: var(--cv-muted); font-family: var(--font-sans); font-size: 14px; font-weight: 500; }
@media (max-width: 1280px) { .headline { display: none; } }
.facts { display: flex; gap: 6px 20px; flex-wrap: wrap; font-size: 14px; font-weight: 500; margin-top: 2px; }
.facts > span { display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }
strong { color: var(--cv-siu); font-weight: 750; }
.guide { display: flex; gap: 10px; padding: 14px; max-width: 380px; font-size: 14px; }
.guide p { margin: 0 0 4px; }
.guide small { color: var(--cv-muted); }
</style>
