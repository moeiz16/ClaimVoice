<script setup lang="ts">
// One row of the screener's board (DESIGN.md §0.2): line key · state (glyph + word + timer) · caller · the
// screener's note ("ClaimVoice asked …" or the hand-off summary) with what was heard · step meter · live level ·
// the actions on the row. Waiting rows offer Take the call; lines offer Listen · Whisper · Take over.
import { motion } from 'motion-v'
import type { BoardRow } from '~/utils/board'
import { LAMP_GLYPH } from '~/utils/board'
import { lossIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'

const props = defineProps<{ row: BoardRow }>()
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
const heard = computed(() => (line.value?.heard ?? []).slice(0, 3))
const STATE_KIND = { urgent: 'urgent', waiting: 'adj', person: 'person', line: 'orchid', ringing: 'plain' } as const

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
    layout class="bl" :class="[`lamp-${r.lamp}`, { on: isOn }]"
    :initial="reduced ? { opacity: 0 } : { opacity: 0, x: r.lamp === 'urgent' ? -40 : 0 }" :animate="{ opacity: 1, x: 0 }"
    :transition="reduced ? { duration: 0.15 } : { type: 'spring', stiffness: 260, damping: 26 }"
    :aria-label="`${r.lineLabel}, ${r.callerLabel}, ${r.stateWord}${isOn ? '. You are listening.' : ''}`"
  >
    <NuxtLink :to="`/lines/${r.callId}`" class="key" :aria-label="`Open ${r.lineLabel}, ${r.callerLabel}`">
      <span class="n num">{{ r.lineNo ?? '·' }}</span>
      <span class="lamp" aria-hidden="true"><UIcon :name="isOn ? 'i-lucide-headphones' : LAMP_GLYPH[r.lamp]" class="size-3.5" /></span>
    </NuxtLink>

    <div class="state">
      <CvTag :kind="isOn ? 'orchid' : STATE_KIND[r.lamp]" :icon="isOn ? 'listen' : LAMP_GLYPH[r.lamp]">{{ isOn ? 'You\'re listening' : r.stateWord }}</CvTag>
      <time class="t num" :class="{ hot: r.lamp === 'urgent' }" :aria-label="waiting ? `Waiting ${clock.elapsed(r.since)}` : `On the line for ${clock.elapsed(r.since)}`">
        <UIcon v-if="waiting" name="i-lucide-clock" class="size-3.5" />{{ clock.elapsed(r.since) }}{{ waiting ? ' waiting' : '' }}
      </time>
    </div>

    <div class="who">
      <h3><NuxtLink :to="`/lines/${r.callId}`">{{ r.callerLabel }}</NuxtLink></h3>
      <p class="what">
        <UIcon :name="icon(lossIcon(line?.lossType))" class="size-4" />{{ [r.place, r.lossTypeLabel].filter(Boolean).join(' · ') }}
        <UBadge v-if="fr" color="primary" variant="soft" size="sm">FR</UBadge>
      </p>
      <div class="level" aria-hidden="true">
        <LiveWave :seed-key="r.callId" :bar="2" :gap="2" />
      </div>
    </div>

    <div class="note">
      <template v-if="r.handoff">
        <p class="said">{{ r.handoff.detail }}</p>
        <p v-if="r.handoff.actionsTaken.length" class="did">
          ClaimVoice {{ r.handoff.actionsTaken.map(a => a.charAt(0).toLowerCase() + a.slice(1)).join('; ') }}.
        </p>
      </template>
      <template v-else-if="line?.lastAsked">
        <small><i aria-hidden="true" />{{ fr ? 'ClaimVoice a demandé' : 'ClaimVoice asked' }}</small>
        <p class="said" :lang="fr ? 'fr' : undefined">{{ fr ? `« ${line.lastAsked.text} »` : `“${line.lastAsked.text}”` }}</p>
        <p v-if="line.lastAsked.textEn" class="tr">{{ line.lastAsked.textEn }}</p>
      </template>
      <div v-if="heard.length" class="heardlist">
        <template v-for="h in heard" :key="h.key">
          <CvTag v-if="h.tone === 'caution'" kind="siu" icon="person">{{ h.text }}</CvTag>
          <span v-else class="heard plain" :lang="fr ? 'fr' : undefined">{{ h.text }}</span>
        </template>
      </div>
    </div>

    <div class="prog">
      <template v-if="line">
        <ScriptProgress :stage="line.stage" />
        <span class="stepl">Step {{ line.stage.step }} of {{ line.stage.steps }} · {{ line.stage.stepLabel }}</span>
        <span class="mood"><UIcon name="i-lucide-heart" class="size-3.5" />{{ line.mood.label }}<template v-if="cardStopped"> · card number stopped</template></span>
      </template>
    </div>

    <div class="acts" :class="{ 'waiting-acts': waiting }">
      <template v-if="waiting">
        <UButton v-if="can('calls:handoff')" :color="r.lamp === 'urgent' ? 'primary' : 'neutral'" icon="i-lucide-phone" @click="take">
          Take the call
        </UButton>
        <UButton v-if="r.lamp === 'urgent' && can('calls:listen')" color="neutral" variant="soft" @click="listening.toggle(asLine)">
          {{ isOn ? 'Listening' : 'Listen first' }}
        </UButton>
        <UButton v-else color="neutral" variant="soft" @click="emit('summary', r)">
          Read the summary
        </UButton>
      </template>
      <UButtonGroup v-else-if="can('calls:listen')" size="lg">
        <UButton :color="isOn ? 'primary' : 'neutral'" :variant="isOn ? 'solid' : 'soft'" icon="i-lucide-headphones" :aria-pressed="isOn" @click="listening.toggle(asLine)">
          {{ isOn ? 'Listening' : 'Listen' }}
        </UButton>
        <UButton v-if="can('calls:whisper')" color="neutral" variant="soft" icon="i-lucide-message-square-more" @click="whisper">
          Whisper
        </UButton>
        <UButton v-if="can('calls:takeover')" color="neutral" icon="i-lucide-phone" :disabled="took" @click="listening.takeoverFor.value = asLine">
          Take over
        </UButton>
      </UButtonGroup>
      <UButton v-else :to="`/lines/${r.callId}`" color="neutral" variant="soft" trailing-icon="i-lucide-arrow-right">
        Open the line
      </UButton>
    </div>
  </motion.li>
</template>

<style scoped>
.bl {
  list-style: none; display: grid; align-items: center; gap: 10px 22px; padding: 14px 32px 14px 24px;
  grid-template-columns: 64px 196px minmax(170px, 1fr) minmax(240px, 1.8fr) 150px auto;
  grid-template-areas: "key state who note prog acts";
  border-bottom: 1px solid var(--cv-rule); background: var(--cv-bg); position: relative;
}
.bl::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: transparent; }
.lamp-urgent { background: color-mix(in srgb, var(--cv-urgent-wash) 70%, var(--cv-bg)); }
.lamp-urgent::before { background: var(--cv-urgent); }
.lamp-waiting::before { background: var(--cv-adj); }
.on { background: color-mix(in srgb, var(--cv-orchid-wash) 75%, var(--cv-bg)); }
.on::before { background: var(--cv-orchid); }
.key {
  grid-area: key; width: 60px; height: 56px; border-radius: 10px; display: grid; place-items: center; align-content: center; gap: 2px;
  background: var(--cv-dock); color: var(--cv-on-dock); text-decoration: none; box-shadow: inset 0 -2px 0 rgba(0, 0, 0, .3);
}
.key .n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 21px; font-weight: 720; line-height: 1; }
.lamp { width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; background: color-mix(in srgb, var(--cv-dock-orchid) 30%, transparent); color: var(--cv-dock-orchid); }
.lamp-waiting .lamp { background: #F2C36B; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-urgent .lamp { background: #FF8070; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-person .lamp { background: #8FAEFF; color: #1F2747; }
.on .lamp { background: var(--cv-dock-orchid); color: #2A1530; animation: none; }
.state { grid-area: state; display: grid; gap: 6px; justify-items: start; }
.t { display: inline-flex; gap: 4px; align-items: center; font-size: 13px; font-weight: 600; color: var(--cv-muted); }
.t.hot { color: var(--cv-urgent); }
.who { grid-area: who; min-width: 0; }
h3 { font-size: 20px; font-weight: 680; line-height: 1.15; }
h3 a { color: inherit; text-decoration: none; }
h3 a:hover { text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 4px; }
.what { margin: 3px 0 0; display: flex; align-items: center; gap: 6px; color: var(--cv-muted); font-size: 13.5px; flex-wrap: wrap; }
.note { grid-area: note; min-width: 0; display: grid; gap: 4px; }
.note small { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 650; color: var(--cv-muted); }
.note small i { width: 7px; height: 7px; border-radius: 50%; background: var(--cv-orchid); }
.said { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 16px; font-weight: 560; line-height: 1.3; }
.did, .tr { margin: 0; color: var(--cv-muted); font-size: 13px; }
.heardlist { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
.heardlist .heard { min-height: 26px; font-size: 12.5px; padding: 2px 10px; }
.prog { grid-area: prog; display: grid; gap: 5px; }
.stepl { font-size: 12.5px; font-weight: 600; color: var(--cv-muted); }
.mood { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--cv-muted); }
.level { height: 30px; margin-top: 8px; max-width: 260px; }
.acts { grid-area: acts; display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; white-space: nowrap; }
.waiting-acts { flex-direction: column; align-items: stretch; }
.state :deep(.cv-tag) { white-space: nowrap; }
@media (max-width: 1440px) {
  .bl { grid-template-columns: 64px 186px minmax(160px, 1fr) minmax(220px, 1.6fr) auto; grid-template-areas: "key state who note acts" "key state who prog acts"; }
  .prog { max-width: 260px; }
}
@media (max-width: 1100px) {
  .bl { grid-template-columns: 64px minmax(0, 1fr) minmax(0, 1fr); grid-template-areas: "key who state" "key note note" "key prog acts"; padding-right: 20px; }
  .state { justify-items: end; }
}
@media (max-width: 720px) {
  .bl { grid-template-columns: 52px minmax(0, 1fr); grid-template-areas: "key who" "state state" "note note" "prog prog" "acts acts"; padding: 14px 16px 14px 18px; gap: 10px 12px; }
  .key { width: 50px; height: 50px; }
  .state { justify-items: start; grid-auto-flow: column; align-items: center; justify-content: start; }
  .acts { justify-content: flex-start; }
  .heardlist > :nth-child(n+3) { display: none; }
}
</style>
