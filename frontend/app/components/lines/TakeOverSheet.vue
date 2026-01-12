<script setup lang="ts">
// Take over: a decision, so it confirms in a dialog (Nuxt UI Modal). After: the person types what to say, the line
// speaks it in its voice, ClaimVoice keeps taking notes, and the take-over is written to the activity log. The desk
// follows by captions, not audio.
import { firstName } from '~/utils/format'

const listening = useListening()
const target = listening.takeoverFor
const busy = ref(false)
const open = computed({ get: () => !!target.value, set: (v: boolean) => { if (!v) target.value = null } })

async function confirm() {
  if (!target.value) return
  busy.value = true
  const t = target.value
  const ok = await listening.takeOver(t)
  busy.value = false
  if (ok) await navigateTo(`/lines/${t.callId}`)
}
</script>

<template>
  <UModal v-model:open="open" :title="target ? `Take over ${firstName(target.callerLabel)}'s call?` : 'Take over'" :description="target ? `${target.lineLabel}${target.place ? ` · ${target.place}` : ''}` : undefined">
    <template #body>
      <div v-if="target" class="grid gap-4">
        <p class="text-[15px]">
          You'll take {{ firstName(target.callerLabel) }}'s call by typing: what you write is spoken to {{ firstName(target.callerLabel) }} in the line's voice. ClaimVoice stops asking questions and keeps taking notes.
        </p>
        <ul class="grid gap-2 text-sm text-muted">
          <li class="flex items-center gap-2"><UIcon name="i-lucide-captions" class="size-4 shrink-0" />You follow the call by live captions here; the desk doesn't play the call's audio.</li>
          <li class="flex items-center gap-2"><UIcon name="i-lucide-file-text" class="size-4 shrink-0" />Everything heard so far stays in the claim file.</li>
          <li class="flex items-center gap-2"><UIcon name="i-lucide-arrow-left-right" class="size-4 shrink-0" />You can hand the call back to ClaimVoice at any point.</li>
          <li class="flex items-center gap-2"><UIcon name="i-lucide-link-2" class="size-4 shrink-0" />The take-over is written to the activity log.</li>
        </ul>
      </div>
    </template>
    <template #footer>
      <div class="flex gap-2 flex-wrap">
        <UButton icon="i-lucide-phone" :loading="busy" autofocus @click="confirm">
          Take the call
        </UButton>
        <UButton color="neutral" variant="soft" @click="target = null">
          Not now
        </UButton>
      </div>
    </template>
  </UModal>
</template>
