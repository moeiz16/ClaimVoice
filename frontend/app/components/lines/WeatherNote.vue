<script setup lang="ts">
// The weather note (DESIGN.md §3): a surge, in words, as a sand note under the page's answer, with the supervisor's
// two levers (the storm's questions; the standby team) and "What's covered" in a popover.
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
const questionsWord = computed(() => `${props.surge.kindLabel} questions ${props.surge.surgeQuestionsOn ? 'on' : 'off'}`)

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
  <section class="wx" role="status" aria-label="Weather on the lines">
    <span class="ic" aria-hidden="true"><UIcon :name="kindIcon" class="size-7" /></span>
    <div class="txt">
      <h2>{{ surge.title }}</h2>
      <p class="hl">
        {{ surge.headline }}
      </p>
      <p class="facts">
        <span v-if="queueWords">{{ queueWords }}</span>
        <span v-else>Calls are <b class="num">{{ surge.multiplier.toFixed(1) }}×</b> usual {{ surge.sinceLabel }}</span>
        <span><UIcon name="i-lucide-clock" class="size-4" />Wait for a person: {{ waitWords }}</span>
        <span v-if="!can('lines:manage')"><UIcon :name="surge.surgeQuestionsOn ? 'i-lucide-check' : 'i-lucide-x'" class="size-4" />{{ questionsWord }}</span>
      </p>
    </div>
    <div class="levers">
      <USwitch v-if="can('lines:manage')" :model-value="surge.surgeQuestionsOn" :label="questionsWord" color="warning" @update:model-value="toggleQuestions" />
      <div class="btns">
        <UButton v-if="can('lines:manage') && !surge.standbyCalled" icon="i-lucide-users-round" :loading="busy" color="neutral" @click="standby">
          Bring in the standby team ({{ surge.standbyAvailable }})
        </UButton>
        <CvTag v-else-if="surge.standbyCalled" kind="fast" icon="check" lg>Standby team on the lines</CvTag>
        <UPopover :content="{ side: 'bottom', align: 'end' }">
          <UButton color="neutral" variant="outline">
            What's covered
          </UButton>
          <template #content>
            <div class="guide">
              <UIcon name="i-lucide-shield-check" class="size-5 text-jade-ink shrink-0" />
              <div>
                <p>{{ surge.guidance }}</p>
                <small>{{ surge.source }}</small>
              </div>
            </div>
          </template>
        </UPopover>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wx { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 16px 20px; align-items: center; padding: 18px 22px; border-radius: 28px; background: var(--cv-sand); }
.ic { width: 60px; height: 60px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-surface); color: var(--cv-caller); }
h2 { font-size: 24px; line-height: 1.1; font-weight: 900; }
.hl { margin: 3px 0 0; color: var(--cv-ink); font-size: 14.5px; }
.facts { margin: 6px 0 0; display: flex; gap: 4px 18px; flex-wrap: wrap; font-size: 14px; color: var(--cv-caller); font-weight: 500; }
.facts > span { display: inline-flex; gap: 6px; align-items: center; }
.facts b { font-weight: 700; }
.levers { display: grid; gap: 10px; justify-items: end; }
.btns { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.guide { display: flex; gap: 10px; padding: 16px; max-width: 380px; font-size: 14px; }
.guide p { margin: 0 0 4px; }
.guide small { color: var(--cv-muted); }
@media (max-width: 1100px) {
  .wx { grid-template-columns: auto minmax(0, 1fr); }
  .levers { grid-column: 1 / -1; justify-items: start; }
  .btns { justify-content: flex-start; }
}
@media (max-width: 720px) {
  .wx { padding: 16px; border-radius: 24px; gap: 12px; }
  .ic { width: 48px; height: 48px; }
  h2 { font-size: 20px; }
}
</style>
