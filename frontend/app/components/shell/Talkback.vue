<script setup lang="ts">
// Talkback: the controls for the line you're listening to, opened from its lit key in the key bank (a Popover).
// Listen is the desk's cue (you follow by captions), Whisper is talkback (ClaimVoice hears it, the caller doesn't),
// Take over puts you on the call. Hand off and Open the call sit underneath.
import { firstName } from '~/utils/format'

const { can } = useSession()
const listening = useListening()
const { onLine } = listening
const clock = useDemoClock()
const text = ref('')
const tookOver = computed(() => onLine.value?.mode === 'took_over')

async function send() {
  if (!onLine.value || !text.value.trim()) return
  if (await listening.whisper(onLine.value.callId, text.value.trim())) text.value = ''
}
</script>

<template>
  <div v-if="onLine" class="tb">
    <div class="who">
      <span class="live-dot" aria-hidden="true" />
      <div>
        <b>{{ onLine.lineLabel }} · {{ onLine.callerLabel }}</b>
        <small v-if="tookOver">You're on the call · ClaimVoice is taking notes</small>
        <small v-else>{{ onLine.language === 'fr' ? 'French · ' : '' }}{{ onLine.place ?? '' }}{{ onLine.place ? ' · ' : '' }}<time class="num">{{ clock.elapsed(onLine.answeredAt) }}</time></small>
      </div>
    </div>
    <div class="wave">
      <LiveWave :seed-key="onLine.callId" :label="`${onLine.callerLabel}'s call, live`" />
    </div>
    <form v-if="!tookOver && can('calls:whisper')" class="say" @submit.prevent="send">
      <UInput v-model="text" maxlength="280" size="lg" class="flex-1" icon="i-lucide-message-square-more" :placeholder="`Whisper to ClaimVoice. ${firstName(onLine.callerLabel)} won't hear this.`" aria-label="Whisper to ClaimVoice" />
      <UButton type="submit" color="neutral" variant="soft" :disabled="!text.trim()">
        Send
      </UButton>
    </form>
    <div class="acts">
      <UButton icon="i-lucide-headphones" color="primary" :aria-pressed="true" @click="listening.stop()">
        {{ tookOver ? 'Leave the call' : 'Stop listening' }}
      </UButton>
      <UButton v-if="!tookOver && can('calls:takeover')" icon="i-lucide-phone" color="neutral" @click="listening.takeoverFor.value = onLine">
        Take over
      </UButton>
      <UButton v-else-if="tookOver" icon="i-lucide-arrow-left-right" color="neutral" @click="listening.giveBack(onLine.callId)">
        Hand back
      </UButton>
      <UButton v-if="can('calls:handoff')" icon="i-lucide-user-round-plus" color="neutral" variant="soft" @click="listening.handoffFor.value = onLine">
        Hand off
      </UButton>
      <UButton :to="`/lines/${onLine.callId}`" color="primary" variant="link" trailing-icon="i-lucide-arrow-right">
        Open the call
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.tb { width: min(420px, calc(100vw - 32px)); padding: 14px; display: grid; gap: 12px; }
.who { display: flex; gap: 10px; align-items: center; }
.who b { display: block; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 17px; font-weight: 680; }
.who small { color: var(--cv-muted); font-size: 13px; }
.wave { height: 46px; }
.say { display: flex; gap: 8px; }
.acts { display: flex; flex-wrap: wrap; gap: 6px; }
</style>
