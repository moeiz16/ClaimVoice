<script setup lang="ts">
// Review and sign off a candidate version: the gates it passed, the side you sign for (claims or model risk), and
// a statement for the activity log. Two different people must sign before it goes into use.
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
  <CvSheet :open="open" :title="check && v ? `Sign off ${check.name}, version ${v.version}` : 'Sign off'" @close="emit('close')">
    <div v-if="check && v">
      <p class="lede">
        You're signing for <b>{{ side }}</b>. When both sides have signed, version {{ v.version }} goes into use and version {{ check.inUse.version }} is retired.
      </p>
      <ul class="gates">
        <li v-for="g in v.gates" :key="g.key" :class="g.passed ? 'ok' : 'no'">
          <CvIcon :name="g.passed ? 'check' : 'x'" size="s" />{{ g.label }}<span class="sr-only-cv">{{ g.passed ? ', passed' : ', did not pass' }}</span>
        </li>
      </ul>
      <label for="so-note">Your statement</label>
      <textarea id="so-note" v-model="note" class="field-input" maxlength="400" />
      <p v-if="error" class="err" role="alert">
        <CvIcon name="urgent" size="s" />{{ error }}
      </p>
      <div class="acts">
        <button class="btn primary" type="button" :disabled="busy || !v.gatesPassed || !note.trim()" @click="sign">
          <CvIcon name="check" />Sign off for {{ side.toLowerCase() }}
        </button>
        <button class="btn soft" type="button" @click="emit('close')">
          Not yet
        </button>
      </div>
    </div>
  </CvSheet>
</template>

<style scoped>
.lede { font-size: 15px; margin: 0 0 12px; }
.gates { list-style: none; margin: 0 0 14px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.gates li { display: inline-flex; gap: 6px; align-items: center; height: 30px; padding: 0 12px 0 10px; border-radius: 999px; font-size: 13px; font-weight: 650; }
.ok { background: var(--cv-fast-wash); color: var(--cv-fast); }
.no { background: var(--cv-urgent-wash); color: var(--cv-urgent); }
label { display: block; font-size: 13px; font-weight: 700; color: var(--cv-muted); margin-bottom: 6px; }
.err { display: flex; gap: 6px; align-items: center; color: var(--cv-urgent); font-weight: 600; font-size: 14px; margin: 10px 0 0; }
.acts { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
</style>
