<script setup lang="ts">
// Hand off from the dock: choose a person or team and add a one-line reason; the call moves into the tray with
// its summary.
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const listening = useListening()
const target = listening.handoffFor
const team = ref<'intake' | 'adjusters' | 'siu'>('intake')
const reason = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const teams = [
  { key: 'intake' as const, label: 'Intake team', sub: 'Jamal, Sofía or Aurélie' },
  { key: 'adjusters' as const, label: 'Adjusters', sub: 'For a claim that needs one now' },
  { key: 'siu' as const, label: 'Special investigations', sub: 'A closer look, never a denial' },
]
const quick = ['Caller wants to talk about a rental', 'Needs a person who speaks French', 'Complicated coverage question', 'Caller is upset']

async function send() {
  if (!target.value) return
  if (!reason.value.trim()) { error.value = 'Add a one-line reason, so nobody asks the caller twice.'; return }
  busy.value = true
  error.value = null
  try {
    await api.calls.handoff(target.value.callId, { reason: reason.value.trim(), team: team.value })
    listening.flash(`${target.value.lineLabel} is in the hand-off tray.`)
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
  <CvSheet :open="!!target" :title="target ? `Hand off ${target.lineLabel}` : ''" @close="target = null">
    <form v-if="target" class="body" @submit.prevent="send">
      <fieldset>
        <legend>Who should take it</legend>
        <label v-for="t in teams" :key="t.key" class="opt" :class="{ on: team === t.key }">
          <input v-model="team" type="radio" name="team" :value="t.key">
          <b>{{ t.label }}</b><span>{{ t.sub }}</span>
        </label>
      </fieldset>
      <label class="lab" for="handoff-reason">Why, in one line</label>
      <input id="handoff-reason" v-model="reason" autofocus class="field-input sm" maxlength="140" :aria-invalid="!!error" placeholder="Caller wants to talk about a rental">
      <div class="quick">
        <button v-for="q in quick" :key="q" class="tag plain" type="button" @click="reason = q">
          {{ q }}
        </button>
      </div>
      <p v-if="error" class="err" role="alert">
        <CvIcon name="urgent" size="s" />{{ error }}
      </p>
      <div class="acts">
        <button class="btn primary" type="submit" :disabled="busy">
          <CvIcon name="handoff" />Hand off with the summary
        </button>
        <button class="btn soft" type="button" @click="target = null">
          Not now
        </button>
      </div>
    </form>
  </CvSheet>
</template>

<style scoped>
fieldset { border: 0; padding: 0; margin: 0 0 14px; display: grid; gap: 8px; }
legend, .lab { font-size: 13px; font-weight: 700; color: var(--cv-muted); margin-bottom: 6px; display: block; }
.opt { display: grid; grid-template-columns: auto 1fr; column-gap: 10px; align-items: center; padding: 10px 16px; border-radius: 999px; background: var(--cv-sunk); cursor: pointer; }
.opt.on { background: var(--cv-orchid-wash); box-shadow: inset 0 0 0 2px var(--cv-orchid); }
.opt input { grid-row: span 2; accent-color: var(--cv-orchid); width: 18px; height: 18px; }
.opt b { font-size: 15px; } .opt span { color: var(--cv-muted); font-size: 13px; }
.quick { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; }
.quick .tag { border: 0; padding: 0 12px; }
.err { display: flex; gap: 6px; align-items: center; color: var(--cv-urgent); font-weight: 600; font-size: 14px; margin: 12px 0 0; }
.acts { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
</style>
