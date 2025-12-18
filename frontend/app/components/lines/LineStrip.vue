<script setup lang="ts">
// A live line as a channel strip (DESIGN.md §5.3): a segmented level meter down its edge, the live conversation
// waveform, what ClaimVoice last asked, the seven-step script progress, what was heard as pills, one plain mood
// word, and Listen · Whisper · Take over at its foot. No scrolling transcript on the desk.
import { motion } from 'motion-v'
import type { LiveLine } from '~/types/api'
import { lossIcon } from '~/utils/labels'

const props = withDefaults(defineProps<{ line: LiveLine, compact?: boolean }>(), { compact: false })
const { can } = useSession()
const listening = useListening()
const clock = useDemoClock()
const isOn = computed(() => listening.onLine.value?.callId === props.line.callId)
const took = computed(() => props.line.listeners.some(l => l.mode === 'took_over'))
const takenBy = computed(() => props.line.listeners.find(l => l.mode === 'took_over')?.name ?? null)
const fr = computed(() => props.line.language === 'fr')
const wave = ref<{ current: { a: number } } | null>(null)
const meter = computed(() => Math.round(18 + (wave.value?.current.a ?? 0.3) * 62))
const reduced = useReducedMotionPref()
const cardStopped = computed(() => props.line.flags.some(f => f.kind === 'card_number_removed'))

async function onWhisper() {
  if (!isOn.value) await listening.listen(props.line)
  listening.whisperOpen.value = true
}
</script>

<template>
  <motion.section
    class="strip" :layout-id="`call-${line.callId}`" :transition="reduced ? { duration: 0.15 } : { type: 'spring', stiffness: 260, damping: 26 }"
    :class="{ listening: isOn, compact, took }" :aria-label="`${line.lineLabel}, ${line.callerLabel}${fr ? ', in French' : ''}${isOn ? '. You are listening.' : ''}`">
    <span class="meter" aria-hidden="true"><i :style="{ height: `${meter}%` }" /></span>
    <div class="head">
      <span class="tag plain">{{ line.lineLabel }}</span>
      <span class="tag" :class="fr ? 'orchid' : 'plain'">{{ fr ? 'FR' : 'EN' }}</span>
      <span v-if="isOn" class="tag orchid"><CvIcon name="listen" size="s" />You're listening</span>
      <span v-else-if="took" class="tag person"><CvIcon name="person" size="s" />{{ takenBy?.split(' ')[0] }} has it</span>
      <time class="t num" :aria-label="`On the line for ${clock.elapsed(line.answeredAt)}`">{{ clock.elapsed(line.answeredAt) }}</time>
    </div>
    <h2><NuxtLink :to="`/lines/${line.callId}`">{{ line.callerLabel }}</NuxtLink></h2>
    <div class="what">
      <CvIcon :name="lossIcon(line.lossType)" size="s" />{{ [line.place, line.lossTypeLabel].filter(Boolean).join(' · ') }}
    </div>
    <div class="wave">
      <LiveWave ref="wave" :seed-key="line.callId" />
    </div>
    <div v-if="line.lastAsked && !compact" class="asking">
      <small><i />{{ fr ? 'ClaimVoice a demandé' : 'ClaimVoice asked' }}</small>
      <p :lang="fr ? 'fr' : undefined">
        {{ fr ? `« ${line.lastAsked.text} »` : `“${line.lastAsked.text}”` }}
      </p>
      <p v-if="line.lastAsked.textEn" class="tr">
        {{ line.lastAsked.textEn }}
      </p>
    </div>
    <ScriptProgress :stage="line.stage" />
    <div class="stepl">
      <span>Step {{ line.stage.step }} of {{ line.stage.steps }} · {{ line.stage.stepLabel }}</span>
      <span>{{ fr ? 'Heard in French' : line.stage.nextLabel ?? '' }}</span>
    </div>
    <div v-if="!compact" class="heardlist">
      <template v-for="h in line.heard" :key="h.key">
        <span v-if="h.tone === 'caution'" class="tag siu"><CvIcon name="person" size="s" />{{ h.text }}</span>
        <span v-else class="heard plain" :lang="fr ? 'fr' : undefined">{{ h.text }}</span>
      </template>
    </div>
    <div class="mood">
      <CvIcon name="heart" size="s" />{{ line.mood.label }}<template v-if="line.mood.detail">
        · {{ line.mood.detail }}
      </template><template v-else-if="cardStopped">
        · card number stopped
      </template>
    </div>
    <div class="ctrls">
      <button v-if="can('calls:listen')" type="button" :class="{ on: isOn }" :aria-pressed="isOn" @click="listening.toggle(line)">
        <CvIcon name="listen" /><span>{{ isOn ? 'Listening' : 'Listen' }}</span>
      </button>
      <button v-if="can('calls:whisper')" type="button" @click="onWhisper">
        <CvIcon name="whisper" /><span>Whisper</span>
      </button>
      <button v-if="can('calls:takeover')" type="button" class="take" :disabled="took" @click="listening.takeoverFor.value = listening.fromLine(line)">
        <CvIcon name="phone" /><span>Take over</span>
      </button>
      <NuxtLink v-if="!can('calls:listen')" :to="`/lines/${line.callId}`" class="open">
        <CvIcon name="right" /><span>Open the line</span>
      </NuxtLink>
    </div>
  </motion.section>
</template>

<style scoped>
.strip { position: relative; background: var(--cv-surface); border-radius: 28px; padding: 16px 16px 14px 28px; display: flex; flex-direction: column; gap: 9px; min-width: 0; transition: box-shadow 200ms; }
.strip.listening { box-shadow: inset 0 0 0 2.5px var(--cv-orchid); }
.meter { position: absolute; left: 12px; top: 22px; bottom: 22px; width: 6px; border-radius: 3px; background: var(--cv-sunk); overflow: hidden; -webkit-mask: repeating-linear-gradient(to top, #000 0 4px, transparent 4px 7px); mask: repeating-linear-gradient(to top, #000 0 4px, transparent 4px 7px); }
.meter i { position: absolute; left: 0; right: 0; bottom: 0; border-radius: 3px; background: linear-gradient(to top, var(--cv-caller) 0 50%, var(--cv-orchid) 50% 100%); transition: height 180ms var(--ease-voice); }
.head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.t { margin-left: auto; font-weight: 700; font-size: 14px; color: var(--cv-muted); }
h2 { font-size: 23px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; }
h2 a { color: inherit; text-decoration: none; }
h2 a:hover { text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 4px; }
.what { display: flex; align-items: center; gap: 7px; color: var(--cv-muted); font-size: 14px; font-weight: 550; margin-top: -6px; }
.wave { height: 44px; }
.asking { background: var(--cv-sunk); border-radius: 20px; padding: 10px 12px; }
.asking small { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 750; color: var(--cv-muted); }
.asking small i { width: 7px; height: 7px; border-radius: 50%; background: var(--cv-orchid); }
.asking p { margin: 3px 0 0; font-family: var(--font-display); font-size: 16px; font-weight: 600; line-height: 1.25; letter-spacing: -0.015em; }
.asking p.tr { font-family: var(--font-sans); font-size: 13px; font-weight: 500; color: var(--cv-muted); letter-spacing: 0; }
.stepl { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; color: var(--cv-muted); font-weight: 600; margin-top: -6px; }
.heardlist { display: flex; flex-wrap: wrap; gap: 6px; }
.heardlist .heard { min-height: 30px; font-size: 13px; padding: 3px 12px; }
.mood { display: flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 600; color: var(--cv-muted); margin-top: auto; }
.ctrls { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.ctrls button, .ctrls a { border: 0; border-radius: 20px; background: var(--cv-sunk); height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; font-size: 13px; font-weight: 650; color: var(--cv-ink); text-decoration: none; }
.ctrls button:hover:not(:disabled), .ctrls a:hover { background: var(--cv-sunk-2); }
.ctrls button.on { background: var(--cv-orchid); color: var(--cv-on-orchid); }
.ctrls button.take { background: var(--cv-ink); color: var(--cv-bg); }
.ctrls a.open { grid-column: 1 / -1; flex-direction: row; gap: 6px; }
.compact h2 { font-size: 19px; }
.compact .ctrls button span { display: none; }
.compact .ctrls button { height: 44px; }
@media (max-width: 720px) {
  .heardlist > :nth-child(n+3) { display: none; }
}
</style>
