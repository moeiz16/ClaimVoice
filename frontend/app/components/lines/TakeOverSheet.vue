<script setup lang="ts">
// Take over: confirm in a sheet. After: the person types what to say, the line speaks it in its voice, ClaimVoice
// keeps taking notes, and the take-over is written to the activity log. The desk follows by captions, not audio.
import { firstName } from '~/utils/format'

const listening = useListening()
const target = listening.takeoverFor
const busy = ref(false)

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
  <CvSheet :open="!!target" :title="target ? `Take over ${firstName(target.callerLabel)}'s call?` : ''" @close="target = null">
    <div v-if="target" class="body">
      <p class="lede">
        You'll take {{ firstName(target.callerLabel) }}'s call by typing: what you write is spoken to {{ firstName(target.callerLabel) }} in the line's voice. ClaimVoice stops asking questions and keeps taking notes.
      </p>
      <ul>
        <li><CvIcon name="captions" size="s" />You follow the call by live captions here; the desk doesn't play the call's audio.</li>
        <li><CvIcon name="doc" size="s" />Everything heard so far stays in the claim file.</li>
        <li><CvIcon name="swap" size="s" />You can hand the call back to ClaimVoice at any point.</li>
        <li><CvIcon name="chain" size="s" />The take-over is written to the activity log.</li>
      </ul>
      <div class="acts">
        <button class="btn primary" type="button" :disabled="busy" autofocus @click="confirm">
          <CvIcon name="phone" />Take the call
        </button>
        <button class="btn soft" type="button" @click="target = null">
          Not now
        </button>
      </div>
    </div>
  </CvSheet>
</template>

<style scoped>
.lede { font-family: var(--font-display); font-size: 19px; font-weight: 550; line-height: 1.35; letter-spacing: -0.01em; margin: 0 0 14px; }
ul { list-style: none; margin: 0 0 20px; padding: 0; display: grid; gap: 8px; color: var(--cv-muted); font-size: 14px; }
li { display: flex; gap: 8px; align-items: center; }
.acts { display: flex; gap: 10px; flex-wrap: wrap; }
</style>
