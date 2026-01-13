<script setup lang="ts">
// Review and sign off a candidate version (a dialog): the gates it passed, the side you sign for (claims or model
// risk), and a statement for the activity log. Two different people must sign before it goes into use.
import type { Check } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const props = defineProps<{ open: boolean, check: Check | null }>()
const emit = defineEmits<{ close: [], signed: [c: Check] }>()
const { role } = useSession()
const note = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const side = computed(() => (role.value === 'supervisor' ? 'Claims' : 'Model risk'))
const v = computed(() => props.check?.candidate ?? null)
const isOpen = computed({ get: () => props.open, set: (o: boolean) => { if (!o) emit('close') } })
watch(() => props.open, (o) => { if (o) { note.value = `I have reviewed version ${v.value?.version ?? ''} and agree it can replace the version in use.`; error.value = null } })

async function sign() {
  if (!props.check || !v.value) return
  busy.value = true
  error.value = null
  try {
    emit('signed', await api.routing.signOff(props.check.key, v.value.version, note.value.trim()))
    emit('close')
  }
  catch (e) {
    error.value = e instanceof ApiError
      ? (e.code === 'already_signed' ? 'This side is already signed, or you signed the other side. Two different people must sign.' : e.code === 'gates_failed' ? 'A check didn\'t pass, so this version can\'t be signed.' : e.message)
      : 'That didn\'t save. Try again.'
  }
  busy.value = false
}
</script>

<template>
  <UModal
    v-model:open="isOpen"
    :title="check && v ? `Sign off ${check.name}, version ${v.version}` : 'Sign off'"
    :description="check && v ? 'Two different people must sign before it goes into use.' : undefined"
  >
    <template #body>
      <div v-if="check && v" class="grid gap-4">
        <p class="text-[15px] m-0">
          You're signing for <b>{{ side }}</b>. When both sides have signed, version {{ v.version }} goes into use and version {{ check.inUse.version }} is retired.
        </p>
        <ul class="gates" aria-label="What this version passed">
          <li v-for="g in v.gates" :key="g.key">
            <CvTag :kind="g.passed ? 'fast' : 'urgent'" :icon="g.passed ? 'check' : 'x'">
              {{ g.label }}<span class="sr-only-cv">{{ g.passed ? ', passed' : ', did not pass' }}</span>
            </CvTag>
          </li>
        </ul>
        <UFormField label="Your statement" name="note" help="Written to the activity log with your name.">
          <UTextarea v-model="note" :maxlength="400" :rows="3" autoresize class="w-full" />
        </UFormField>
        <UAlert v-if="error" color="error" variant="soft" icon="i-lucide-triangle-alert" :title="error" role="alert" />
      </div>
    </template>
    <template #footer>
      <div v-if="check && v" class="flex gap-2 flex-wrap">
        <UButton icon="i-lucide-check" :loading="busy" :disabled="busy || !v.gatesPassed || !note.trim()" autofocus @click="sign">
          Sign off for {{ side.toLowerCase() }}
        </UButton>
        <UButton color="neutral" variant="soft" @click="emit('close')">
          Not yet
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.gates { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
</style>
