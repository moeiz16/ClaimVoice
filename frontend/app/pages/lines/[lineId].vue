<script setup lang="ts">
// The live call / listen view (DESIGN.md §5.2): the conversation with a time column (the current turn large, interim
// words settling), whisper rows, the claim file filling in with ▸ moment chips, the script track and the safety
// watch. Keyboard: L listen, W whisper, T take over.
import type { Turn } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, zoneLabel } from '~/utils/format'
import { marksByTurn, slotByKey } from '~/utils/marks'
import { ApiError } from '~/utils/http'

const route = useRoute()
const id = computed(() => String(route.params.lineId))
const { state, line, status, error, retained, notice, reload } = useCallStream(id)
const { can, me } = useSession()
const listening = useListening()
const links = useHeardLinks()
const clock = useDemoClock()
const call = computed(() => state.value.call)
useHead(() => ({ title: `${call.value?.callerLabel ?? 'On the line'} · ClaimVoice` }))

const fr = computed(() => call.value?.language === 'fr')
const showEn = ref(true)
const reading = ref(false)
const pane = ref<'convo' | 'file'>('convo')
const ended = computed(() => call.value?.state === 'ended' || !!state.value.ended)
const myTake = computed(() => call.value?.listeners.some(l => l.mode === 'took_over' && l.userId === me.value?.user.id) || (listening.onLine.value?.callId === id.value && listening.onLine.value.mode === 'took_over'))
const turns = computed(() => state.value.turns)
const marks = computed(() => marksByTurn(state.value.file))
const hushCount = computed(() => turns.value.reduce((n, t) => n + t.redactions, 0))
const at = (t: Turn) => fmtClock(t.atMs / 1000)
const lastIdx = computed(() => {
  for (let i = turns.value.length - 1; i >= 0; i--) if (turns.value[i]!.speaker !== 'whisper' && turns.value[i]!.speaker !== 'system') return i
  return -1
})
const partial = computed(() => state.value.partial)
const subline = computed(() => {
  const c = call.value
  if (!c) return ''
  return [c.lineLabel ?? line.value?.lineLabel, c.place ?? line.value?.place, c.lossTypeLabel].filter(Boolean).join(' · ')
})
const consent = computed(() => {
  const c = call.value?.consent
  if (!c) return null
  const firstTurn = turns.value.find(t => t.id === c.turnId)
  const when = firstTurn ? ` · ${at(firstTurn)}` : ''
  if (c.answer === 'given') return { kind: 'fast' as const, text: `Recording consent${when}` }
  if (c.answer === 'not_required') return { kind: 'fast' as const, text: 'Recording announced' }
  if (c.answer === 'refused') return { kind: 'urgent' as const, text: 'Asked not to record' }
  return { kind: 'siu' as const, text: 'Waiting for consent' }
})

// Auto-listen: opening a live line puts it in the dock.
let autoListened = ''
watch([call, line], ([c, l]) => {
  if (!c || !l || autoListened === c.id) return
  autoListened = c.id
  if (c.state !== 'ended' && can('calls:listen') && listening.onLine.value?.callId !== c.id) void listening.listen(l)
})

// Scroll the conversation to the newest turn.
const turnsEl = ref<HTMLElement | null>(null)
watch(() => [turns.value.length, partial.value], async () => {
  await nextTick()
  if (turnsEl.value && !reading.value) turnsEl.value.scrollTop = turnsEl.value.scrollHeight
})

function onSpan(turnId: string, key: string) {
  const s = slotByKey(state.value.file, key)
  if (s?.span) links.flash(s.span, false)
  else links.flash({ turnId, start: 0, end: 0 }, false)
  pane.value = 'file'
}

// Whisper / say
const text = ref('')
const sendErr = ref<string | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
async function send() {
  const t = text.value.trim()
  if (!t || !call.value) return
  sendErr.value = null
  if (myTake.value) {
    try { await api.calls.say(call.value.id, t); text.value = '' }
    catch (e) { sendErr.value = e instanceof ApiError && e.code === 'not_taken_over' ? 'Take over the call first.' : 'That didn\'t reach the caller. Try again.' }
  }
  else if (await listening.whisper(call.value.id, t)) text.value = ''
}

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable)) return
  if (e.metaKey || e.ctrlKey || e.altKey || !call.value || !line.value) return
  const k = e.key.toLowerCase()
  if (k === 'l' && can('calls:listen')) void listening.toggle(line.value)
  else if (k === 'w' && can('calls:whisper')) { e.preventDefault(); inputEl.value?.focus() }
  else if (k === 't' && can('calls:takeover')) listening.takeoverFor.value = listening.fromLine(line.value)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
const whoName = (t: Turn) => (t.speaker === 'caller' ? firstName(/^(caller|appelant)$/i.test(t.speakerLabel) ? (call.value?.callerLabel ?? t.speakerLabel) : t.speakerLabel) : t.speakerLabel)
</script>

<template>
  <div class="live" :data-pane="pane">
    <PageHeader :title="call?.callerLabel ?? 'On the line'" :back="{ to: '/lines', label: 'Lines' }">
      <template #caption>
        {{ subline }}<template v-if="call && !ended">
          · <time class="num">{{ clock.elapsed(call.startedAt) }}</time>
        </template><template v-else-if="ended">
          · ended
        </template>
      </template>
      <span v-if="consent" class="tag consent" :class="consent.kind" :title="call?.consent.ruleLabel"><CvIcon name="shield" size="s" /><span class="ct">{{ consent.text }}</span></span>
      <div v-if="fr" class="seg hide-phone" role="group" aria-label="Transcript language">
        <button type="button" :aria-pressed="!showEn" @click="showEn = false">
          Français
        </button>
        <button type="button" :aria-pressed="showEn" @click="showEn = true">
          + English
        </button>
      </div>
      <div class="seg hide-phone" role="group" aria-label="How to follow the call">
        <button type="button" :aria-pressed="!reading" @click="reading = false">
          <CvIcon name="captions" size="s" />Captions
        </button>
        <button type="button" :aria-pressed="reading" @click="reading = true">
          Read instead
        </button>
      </div>
    </PageHeader>

    <div class="pad">
      <ScriptTrack v-if="call" :stage="call.stage" :ended="ended" />
      <span v-else class="skeleton" style="height: 46px; display: block" />
      <StateNote v-if="status === 'lost'" kind="error" title="We lost the connection to this line." body="The call carries on; ClaimVoice keeps taking it. Reconnecting…" retry @retry="reload" />
      <StateNote v-if="error" kind="error" title="We couldn't open this line." :body="error" retry @retry="reload" />
      <div v-if="myTake" class="onit" role="status">
        <CvIcon name="phone" />You're on the call with {{ firstName(call?.callerLabel ?? '') }}. ClaimVoice is taking notes.
        <button class="btn sm soft on-sunk" type="button" @click="listening.giveBack(id)">
          <CvIcon name="swap" size="s" />Hand back to ClaimVoice
        </button>
      </div>
    </div>

    <div class="seg mswitch" role="tablist" aria-label="Show">
      <button type="button" role="tab" :aria-selected="pane === 'convo'" @click="pane = 'convo'">
        Conversation
      </button>
      <button type="button" role="tab" :aria-selected="pane === 'file'" @click="pane = 'file'">
        Claim file
      </button>
    </div>

    <main class="split" :class="{ shorter: myTake || status === 'lost' }">
      <section class="convo" aria-label="Conversation">
        <div class="bar">
          <h2>Conversation{{ fr ? ' · heard in French' : '' }}</h2>
          <div class="r">
            <span class="tag plain"><CvIcon name="lock" size="s" />{{ hushCount ? `${hushCount} moment${hushCount > 1 ? 's' : ''} removed` : 'Nothing removed' }}</span>
          </div>
        </div>
        <div ref="turnsEl" class="turns" :class="{ reading }" aria-live="polite" aria-relevant="additions">
          <p v-if="!retained" class="refused">
            <CvIcon name="shield" size="s" />{{ notice ?? 'Recording stopped at the caller\'s request. Notes only from here.' }}
          </p>
          <template v-if="status === 'loading'">
            <div v-for="n in 3" :key="n" class="turn">
              <span /><div><span class="skeleton" style="display:block; width: 30%; height: 12px; margin-bottom: 8px" /><span class="skeleton" style="display:block; width: 90%; height: 18px" /></div>
            </div>
          </template>
          <div
            v-for="(t, i) in turns" :key="t.id" class="turn"
            :class="[t.speaker, { now: i === lastIdx && !reading && !ended && !partial, interrupted: t.interrupted }]"
          >
            <time class="num">{{ at(t) }}</time>
            <div>
              <div class="who">
                <i />{{ t.speaker === 'whisper' ? 'Whisper, ClaimVoice only' : whoName(t) }}
              </div>
              <p v-if="t.speaker === 'whisper'" class="whisper-p">
                <CvIcon name="whisper" size="s" />{{ t.speakerLabel.split('·')[1]?.trim() ?? '' }}{{ t.speakerLabel.includes('·') ? ': ' : '' }}{{ t.text }}
              </p>
              <p v-else-if="t.speaker === 'system'" class="sys">
                {{ t.text }}
              </p>
              <p v-else :lang="t.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="t.text" :turn-id="t.id" :marks="marks[t.id]" @span="k => onSpan(t.id, k)" />
              </p>
              <span v-if="t.textEn && fr && showEn" class="tr">{{ t.textEn }}</span>
            </div>
          </div>
          <div v-if="partial && !ended" class="turn caller now" aria-hidden="true">
            <time class="num">{{ clock.elapsed(call?.startedAt) }}</time>
            <div>
              <div class="who">
                <i />{{ firstName(call?.callerLabel ?? 'Caller') }} <span class="hearing">hearing now</span>
              </div>
              <p><span v-for="(w, i) in partial.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ w }} </span></p>
            </div>
          </div>
          <p v-if="ended" class="sys end">
            <CvIcon name="check" size="s" />The call has ended.<template v-if="call?.claimNumber">
              Claim {{ call.claimNumber }} is filed.
            </template>
          </p>
        </div>
        <form v-if="!ended && (can('calls:whisper') || myTake)" class="whisperbox" :class="{ say: myTake }" @submit.prevent="send">
          <CvIcon :name="myTake ? 'phone' : 'whisper'" />
          <label class="sr-only-cv" for="line-input">{{ myTake ? 'Say to the caller' : 'Whisper to ClaimVoice' }}</label>
          <input
            id="line-input" ref="inputEl" v-model="text" maxlength="280" autocomplete="off"
            :placeholder="myTake ? `Type what to say to ${firstName(call?.callerLabel ?? '')}. It's spoken in the line's voice.` : `Whisper to ClaimVoice${fr ? ' in English or French' : ''}. ${firstName(call?.callerLabel ?? 'The caller')} won't hear this.`"
          >
          <button class="btn sm soft on-sunk" type="submit" :disabled="!text.trim()">
            {{ myTake ? 'Say it' : 'Send' }}
          </button>
        </form>
        <p v-if="sendErr" class="senderr" role="alert">
          {{ sendErr }}
        </p>
      </section>

      <ClaimFilePanel :file="state.file" :reference="call?.claimNumber" :language="call?.language" :ended="ended">
        <template #top>
          <EndRoute v-if="ended && call?.claimId" :claim-id="call.claimId" />
        </template>
      </ClaimFilePanel>
    </main>
    <p class="zone sr-only-cv">
      Times are minutes into the call. Clock: {{ zoneLabel(line?.region) }}.
    </p>
  </div>
</template>

<style scoped>
.pad { margin: 0 32px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; }
.consent .ct { white-space: nowrap; }
.onit { display: flex; align-items: center; gap: 10px; padding: 10px 10px 10px 16px; border-radius: 28px; background: var(--cv-person-wash); color: var(--cv-person); font-weight: 650; }
.onit .btn { margin-left: auto; }
.mswitch { display: none; }
.split { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 18px; margin: 16px 32px 0; height: calc(100dvh - 72px - 62px - 128px); min-height: 520px; }
.split.shorter { height: calc(100dvh - 72px - 62px - 128px - 70px); }
.convo { background: var(--cv-surface); border-radius: 28px; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
.convo .bar { display: flex; align-items: center; gap: 10px; padding: 14px 20px 8px; }
.convo .bar h2 { font-size: 19px; font-weight: 700; }
.convo .bar .r { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.turns { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 6px; padding: 40px 20px 6px; -webkit-mask: linear-gradient(to bottom, transparent 0, #000 70px); mask: linear-gradient(to bottom, transparent 0, #000 70px); scrollbar-width: thin; }
.turns.reading { mask: none; -webkit-mask: none; padding-top: 6px; }
.turn { display: grid; grid-template-columns: 46px 1fr; gap: 8px; padding: 6px 0; font-size: calc(15.5px * var(--cv-caption-scale)); line-height: 1.5; }
.turn time { color: var(--cv-faint); font-size: 12.5px; font-weight: 650; padding-top: 3px; }
.who { font-weight: 750; font-size: 12.5px; display: flex; align-items: center; gap: 6px; color: var(--cv-muted); }
.who i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); }
.caller .who i { background: var(--cv-caller); }
.person .who i, .whisper .who i { background: var(--cv-person); }
.system .who i { background: var(--cv-faint); }
.caller p { color: var(--cv-caller); }
.person p { color: var(--cv-person); }
.turn p { margin: 1px 0 0; }
.tr { display: block; color: var(--cv-muted); font-size: 13.5px; margin-top: 2px; }
.whisper-p { background: var(--cv-person-wash); color: var(--cv-person); border-radius: 14px; padding: 8px 12px; font-weight: 600; font-size: 14px; display: inline-flex !important; gap: 8px; align-items: center; }
.sys { color: var(--cv-muted); font-style: italic; font-size: 14px; }
.sys.end { display: flex; gap: 6px; align-items: center; font-style: normal; font-weight: 600; padding: 10px 0 0 54px; }
.refused { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; background: var(--cv-sunk); border-radius: 14px; padding: 8px 12px; }
.turn.now { padding: 10px 0 4px; }
.turn.now p { font-family: var(--font-display); font-size: calc(29px * var(--cv-caption-scale)); font-weight: 650; line-height: 1.2; letter-spacing: -0.02em; }
.turn.now .tr { font-size: 15px; }
.hearing { font-weight: 650; color: var(--cv-orchid-ink); font-size: 11.5px; margin-left: 4px; }
.interrupted p::after { content: " …"; color: var(--cv-faint); }
.whisperbox { display: flex; align-items: center; gap: 10px; margin: 6px 14px 14px; padding: 6px 6px 6px 16px; border-radius: 999px; background: var(--cv-sunk); color: var(--cv-person); }
.whisperbox.say { background: var(--cv-person-wash); }
.whisperbox input { flex: 1; border: 0; background: transparent; font: inherit; color: var(--cv-ink); font-size: 14.5px; min-width: 0; height: 38px; }
.whisperbox input:focus { outline: none; }
.whisperbox input::placeholder { color: var(--cv-muted); }
.senderr { margin: -8px 20px 12px; color: var(--cv-urgent); font-size: 13px; font-weight: 600; }
@media (max-width: 720px) {
  .pad { margin: 0 16px; }
  .consent .ct { display: none; }
  .consent { padding: 0 9px; }
  .mswitch { display: flex; margin: 12px 16px 0; }
  .mswitch button { flex: 1; }
  .split { grid-template-columns: 1fr; margin: 12px 16px 0; height: auto; min-height: 0; }
  .live[data-pane="convo"] :deep(.file), .live[data-pane="file"] .convo { display: none; }
  .turns { mask: none; -webkit-mask: none; padding-top: 6px; overflow: visible; }
  .turn:nth-last-child(n+7) { display: none; }
  .turn { grid-template-columns: 38px 1fr; font-size: 15px; }
  .turn.now p { font-size: 22px; }
  .convo .bar .r { display: none; }
  .whisperbox { margin: 6px 10px 12px; }
}
</style>
