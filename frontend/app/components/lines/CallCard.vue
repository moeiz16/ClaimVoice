<script setup lang="ts">
// One caller on the Lines page (DESIGN.md §3), as a speech-bubble card. A caller waiting for a person gets the wide
// card: a wait ring, the state in a word with its glyph and timer, what they need in a sand bubble, what ClaimVoice
// already did, and Take the call. A caller talking with ClaimVoice gets the compact card: a step ring, the last
// question in a jade bubble, the answers heard so far as pebbles, and round Listen · Whisper · Take over buttons.
import { motion } from 'motion-v'
import type { BoardRow } from '~/utils/board'
import { LAMP_GLYPH } from '~/utils/board'
import { lossIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'
import { initials } from '~/utils/format'

const props = defineProps<{ row: BoardRow, index?: number }>()
const emit = defineEmits<{ summary: [row: BoardRow] }>()
const { can } = useSession()
const listening = useListening()
const clock = useDemoClock()
const reduced = useReducedMotionPref()
const r = computed(() => props.row)
const line = computed(() => r.value.line)
const isOn = computed(() => listening.onLine.value?.callId === r.value.callId)
const waiting = computed(() => r.value.lamp === 'urgent' || r.value.lamp === 'waiting')
const fr = computed(() => r.value.language === 'fr')
const took = computed(() => r.value.lamp === 'person')
const asLine = computed(() => listening.fromLine({ callId: r.value.callId, lineLabel: r.value.lineLabel, callerLabel: r.value.callerLabel, place: r.value.place, language: r.value.language, answeredAt: line.value?.answeredAt ?? r.value.since }))
const cardStopped = computed(() => !!line.value?.flags.some(f => f.kind === 'card_number_removed'))
const heard = computed(() => (line.value?.heard ?? []).slice(0, 4))
const tone = computed(() => (r.value.lamp === 'urgent' ? 'urgent' : r.value.lamp === 'waiting' ? 'siu' : r.value.lamp === 'person' ? 'person' : 'jade'))
const where = computed(() => [r.value.lineLabel, r.value.place, r.value.lossTypeLabel].filter(Boolean).join(' · '))

async function take() {
  if (await listening.acceptHandoff(asLine.value)) await navigateTo(`/lines/${r.value.callId}`)
}
async function whisper() {
  if (!isOn.value) await listening.listen(asLine.value)
  await navigateTo(`/lines/${r.value.callId}?whisper=1`)
}
</script>

<template>
  <motion.li
    layout class="cc" :class="[waiting ? 'wide' : 'compact', `lamp-${r.lamp}`, { on: isOn }]"
    :initial="reduced ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.98 }" :animate="{ opacity: 1, y: 0, scale: 1 }"
    :transition="reduced ? { duration: 0.12 } : { type: 'spring', stiffness: 300, damping: 28, delay: (index ?? 0) * 0.04 }"
    :aria-label="`${r.callerLabel}, ${r.stateWord}${isOn ? '. You are listening.' : ''}`"
  >
    <div class="head">
      <StepRing
        v-if="!waiting && line" :stage="line.stage" :initials="initials(r.callerLabel)" :label="r.callerLabel" :tone="tone" :size="60"
      />
      <StepRing v-else :wait-seconds="clock.since(r.since)" :of="180" :initials="initials(r.callerLabel)" :label="`${r.callerLabel}, waiting ${clock.elapsed(r.since)}`" :tone="tone" :size="waiting ? 76 : 60" />
      <div class="who">
        <h3><NuxtLink :to="`/lines/${r.callId}`">{{ r.callerLabel }}</NuxtLink></h3>
        <p class="where">
          <UIcon :name="icon(lossIcon(line?.lossType))" class="size-4" />{{ where }}
          <span v-if="fr" class="fr" title="In French">FR</span>
        </p>
      </div>
      <div class="state">
        <span class="sw" :class="`s-${isOn ? 'on' : r.lamp}`">
          <UIcon :name="isOn ? 'i-lucide-headphones' : LAMP_GLYPH[r.lamp]" class="size-4" />{{ isOn ? 'You\'re listening' : r.stateWord }}
        </span>
        <time class="t num" :aria-label="waiting ? `Waiting ${clock.elapsed(r.since)}` : `On the line for ${clock.elapsed(r.since)}`">
          {{ clock.elapsed(r.since) }}<small v-if="waiting"> waiting</small>
        </time>
      </div>
    </div>

    <!-- What they need, or what ClaimVoice last asked -->
    <template v-if="r.handoff">
      <p class="bubble caller">
        {{ r.handoff.detail }}
      </p>
      <p v-if="r.handoff.actionsTaken.length" class="did">
        <UIcon name="i-lucide-check" class="size-4" />ClaimVoice {{ r.handoff.actionsTaken.map(a => a.charAt(0).toLowerCase() + a.slice(1)).join('; ') }}.
      </p>
    </template>
    <div v-else-if="line?.lastAsked" class="asked">
      <p class="bubble jade" :lang="fr ? 'fr' : undefined">
        <small>{{ fr ? 'ClaimVoice a demandé' : 'ClaimVoice asked' }}</small>
        {{ line.lastAsked.text }}
      </p>
      <p v-if="line.lastAsked.textEn" class="tr">
        {{ line.lastAsked.textEn }}
      </p>
    </div>

    <ul v-if="heard.length" class="heardlist" aria-label="Heard so far">
      <li v-for="h in heard" :key="h.key">
        <CvTag v-if="h.tone === 'caution'" kind="siu" icon="person">{{ h.text }}</CvTag>
        <span v-else class="heard plain" :lang="fr ? 'fr' : undefined"><UIcon name="i-lucide-check" class="size-3.5 text-jade-ink" />{{ h.text }}</span>
      </li>
    </ul>

    <p v-if="line && !waiting" class="prog">
      Step {{ line.stage.step }} of {{ line.stage.steps }} · {{ line.stage.stepLabel }}
      <span class="mood"><UIcon name="i-lucide-heart" class="size-3.5" />{{ line.mood.label }}<template v-if="cardStopped"> · card number stopped</template></span>
    </p>

    <div class="acts">
      <template v-if="waiting">
        <UButton v-if="can('calls:handoff')" size="xl" :color="r.lamp === 'urgent' ? 'error' : 'primary'" icon="i-lucide-phone" @click="take">
          Take the call
        </UButton>
        <UButton v-if="r.lamp === 'urgent' && can('calls:listen')" size="xl" color="neutral" variant="soft" icon="i-lucide-headphones" :aria-pressed="isOn" @click="listening.toggle(asLine)">
          {{ isOn ? 'Listening' : 'Listen first' }}
        </UButton>
        <UButton v-else size="xl" color="neutral" variant="soft" icon="i-lucide-text" @click="emit('summary', r)">
          Read the summary
        </UButton>
      </template>
      <template v-else-if="can('calls:listen')">
        <RoundButton icon="i-lucide-headphones" :label="isOn ? 'Listening' : 'Listen'" :pressed="isOn" @click="listening.toggle(asLine)" />
        <RoundButton v-if="can('calls:whisper')" icon="i-lucide-message-circle-more" label="Whisper" @click="whisper" />
        <RoundButton v-if="can('calls:takeover')" icon="i-lucide-phone" label="Take over" :disabled="took" @click="listening.takeoverFor.value = asLine" />
        <RoundButton icon="i-lucide-arrow-up-right" label="Open" :to="`/lines/${r.callId}`" />
      </template>
      <UButton v-else :to="`/lines/${r.callId}`" color="neutral" variant="soft" trailing-icon="i-lucide-arrow-right">
        Open the call
      </UButton>
    </div>
  </motion.li>
</template>

<style scoped>
.cc { list-style: none; display: flex; flex-direction: column; gap: 12px; padding: 18px 20px 18px; border-radius: 28px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); min-width: 0; }
.cc.on { box-shadow: inset 0 0 0 3px var(--cv-jade), var(--cv-shadow-soft); }
.wide { padding: 22px 24px; gap: 14px; }
.lamp-urgent { background: linear-gradient(180deg, var(--cv-urgent-wash), var(--cv-surface) 70%); }
.lamp-waiting { background: linear-gradient(180deg, var(--cv-siu-wash), var(--cv-surface) 70%); }
.head { display: flex; align-items: center; gap: 14px; min-width: 0; }
.who { min-width: 0; flex: 1; }
h3 { font-size: 22px; line-height: 1.1; font-weight: 900; letter-spacing: -0.015em; }
.wide h3 { font-size: 28px; }
h3 a { color: inherit; text-decoration: none; }
h3 a:hover { text-decoration: underline; text-decoration-thickness: 3px; text-underline-offset: 5px; text-decoration-color: var(--cv-seaglass); }
.where { margin: 3px 0 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; color: var(--cv-muted); font-size: 13.5px; }
.fr { padding: 0 8px; border-radius: 999px; background: var(--cv-jade-wash); color: var(--cv-jade-ink); font-weight: 600; font-size: 12px; }
.state { display: grid; justify-items: end; gap: 4px; text-align: right; flex: none; }
.sw { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: 13px; font-weight: 600; white-space: nowrap; background: var(--cv-jade-wash); color: var(--cv-jade-ink); }
.s-urgent { background: var(--cv-urgent); color: #fff; }
.s-waiting { background: var(--cv-siu-wash); color: var(--cv-siu); box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--cv-siu) 30%, transparent); }
.s-person { background: var(--cv-person-wash); color: var(--cv-person); }
.s-on { background: var(--cv-jade); color: var(--cv-on-jade); }
.s-ringing { background: var(--cv-sunk); color: var(--cv-muted); }
[data-theme="dark"] .s-urgent { color: var(--cv-bg); }
.t { font-family: var(--font-round); font-weight: 900; font-size: 22px; line-height: 1; letter-spacing: -0.01em; }
.t small { font-family: var(--font-sans); font-size: 12px; font-weight: 500; color: var(--cv-muted); letter-spacing: 0; }
.wide .t { font-size: 30px; }
.lamp-urgent .t { color: var(--cv-urgent); }

/* Speech bubbles: the caller's in sand with its tail at the top left; ClaimVoice's in jade wash. */
.bubble { position: relative; margin: 4px 0 0; padding: 12px 16px; border-radius: 6px 22px 22px 22px; font-size: 15.5px; line-height: 1.45; }
.bubble small { display: block; font-size: 12px; font-weight: 600; color: var(--cv-jade-ink); margin-bottom: 2px; }
.bubble.caller { background: var(--cv-sand); color: var(--cv-ink); font-size: 18px; font-weight: 400; }
.bubble.jade { background: var(--cv-jade-wash); color: var(--cv-ink); }
.wide .bubble.caller { font-family: var(--font-round); font-weight: 800; font-size: 21px; line-height: 1.3; letter-spacing: -0.005em; }
.did { margin: 0; display: flex; gap: 6px; align-items: flex-start; color: var(--cv-muted); font-size: 14px; }
.did .size-4 { color: var(--cv-jade-ink); margin-top: 2px; flex: none; }
.tr { margin: 4px 0 0 16px; color: var(--cv-muted); font-size: 13px; }
.heardlist { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.heardlist .heard { min-height: 30px; font-size: 13px; padding: 2px 12px 2px 9px; gap: 5px; }
.prog { margin: 0; display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; color: var(--cv-muted); font-weight: 500; }
.mood { display: inline-flex; align-items: center; gap: 5px; font-weight: 400; }
.acts { display: flex; gap: 8px 10px; flex-wrap: wrap; margin-top: auto; padding-top: 4px; }
.compact .acts { justify-content: space-between; padding-top: 10px; border-top: 2px solid var(--cv-sunk); }
@media (max-width: 720px) {
  .cc, .wide { padding: 16px; border-radius: 24px; }
  .head { flex-wrap: wrap; }
  .state { width: 100%; grid-auto-flow: column; justify-content: space-between; align-items: center; }
  .wide h3 { font-size: 24px; }
  .wide .bubble.caller { font-size: 18px; }
  .acts :deep(button) { flex: 1 1 auto; }
}
</style>
