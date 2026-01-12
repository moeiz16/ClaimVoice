<script setup lang="ts">
// Hand off from the line you're on: choose a team (radio cards) and add a one-line reason; the call joins the board
// as "waiting for a person" with its summary, so nobody asks the caller twice. A dialog, because it is a decision.
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const listening = useListening()
const target = listening.handoffFor
const team = ref<'intake' | 'adjusters' | 'siu'>('intake')
const reason = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const open = computed({ get: () => !!target.value, set: (v: boolean) => { if (!v) target.value = null } })
const teams = [
  { value: 'intake', label: 'Intake team', description: 'Jamal, Sofía or Aurélie' },
  { value: 'adjusters', label: 'Adjusters', description: 'For a claim that needs one now' },
  { value: 'siu', label: 'Special investigations', description: 'A closer look, never a denial' },
]
const quick = ['Caller wants to talk about a rental', 'Needs a person who speaks French', 'Complicated coverage question', 'Caller is upset']

async function send() {
  if (!target.value) return
  if (!reason.value.trim()) { error.value = 'Add a one-line reason, so nobody asks the caller twice.'; return }
  busy.value = true
  error.value = null
  try {
    await api.calls.handoff(target.value.callId, { reason: reason.value.trim(), team: team.value })
    listening.flash(`${target.value.lineLabel} is waiting for a person on the board.`)
    target.value = null
    reason.value = ''
  }
  catch (e) {
    error.value = e instanceof ApiError ? (e.fieldError('reason') ?? e.message) : 'That didn\'t go through. Try again.'
  }
  busy.value = false
}
</script>

<template>
  <UModal v-model:open="open" :title="target ? `Hand off ${target.lineLabel}` : 'Hand off'" :description="target ? `${target.callerLabel}${target.place ? ` · ${target.place}` : ''}` : undefined">
    <template #body>
      <form v-if="target" id="handoff-form" class="grid gap-4" @submit.prevent="send">
        <URadioGroup v-model="team" legend="Who should take it" :items="teams" variant="card" color="primary" />
        <UFormField label="Why, in one line" name="reason" :error="error ?? undefined">
          <UInput v-model="reason" autofocus maxlength="140" class="w-full" placeholder="Caller wants to talk about a rental" />
        </UFormField>
        <div class="flex flex-wrap gap-1.5">
          <UButton v-for="q in quick" :key="q" size="sm" color="neutral" variant="soft" class="rounded-full" @click="reason = q">
            {{ q }}
          </UButton>
        </div>
      </form>
    </template>
    <template #footer>
      <div class="flex gap-2 flex-wrap">
        <UButton type="submit" form="handoff-form" icon="i-lucide-user-round-plus" :loading="busy">
          Hand off with the summary
        </UButton>
        <UButton color="neutral" variant="soft" @click="target = null">
          Not now
        </UButton>
      </div>
    </template>
  </UModal>
</template>
