<script setup lang="ts">
// The live call (DESIGN.md §3): the crumb and the caller's name, then the in-call stage (the caller in a step ring,
// the state in a word, round Listen · Whisper · Take over · Hand off · Read buttons, the safety watch) beside the
// conversation as speech bubbles: Captions shows the latest exchange large, Read shows the whole call. The
// whisper / say field sits under the bubbles like a message field. Under them the answer sheet fills in, question by
// question; when the call ends, where it goes. Keyboard: L listen, W whisper, T take over. ?whisper=1 focuses it.
import type { LevelSource } from '~/composables/useLiveLevels'
import type { Slot, Turn } from '~/types/api'
import { linkKey } from '~/composables/useHeardLinks'
import { api } from '~/utils/api'
import { LAMP_GLYPH } from '~/utils/board'
import type { Lamp } from '~/utils/board'
import { firstName, fmtClock, initials, zoneLabel } from '~/utils/format'
import { ApiError } from '~/utils/http'
import { marksByTurn, slotByKey } from '~/utils/marks'
import { buildNotice } from '~/utils/notice'

const route = useRoute()
const id = computed(() => String(route.params.lineId))
const { state, line, status, error, retained, notice, reload } = useCallStream(id)
const { can, me } = useSession()
const listening = useListening()
const links = useHeardLinks()
const clock = useDemoClock()
const prefs = usePrefs()
const call = computed(() => state.value.call)
useHead(() => ({ title: `${call.value?.callerLabel ?? 'On the line'} · ClaimVoice` }))

const fr = computed(() => call.value?.language === 'fr')
const lang = computed(() => (fr.value ? 'fr' : undefined))
const ended = computed(() => call.value?.state === 'ended' || !!state.value.ended)
const isOn = computed(() => listening.onLine.value?.callId === id.value)
const myTake = computed(() => call.value?.listeners.some(l => l.mode === 'took_over' && l.userId === me.value?.user.id) || (isOn.value && listening.onLine.value?.mode === 'took_over'))
const turns = computed(() => state.value.turns)
const marks = computed(() => marksByTurn(state.value.file))
const hushCount = computed(() => turns.value.reduce((n, t) => n + t.redactions, 0))
const partial = computed(() => state.value.partial)
const at = (t: Turn) => fmtClock(t.atMs / 1000)
const callerFirst = computed(() => firstName(call.value?.callerLabel ?? 'The caller'))

// Transcript language: French calls show the French first, with an English line under each turn for staff.
const langView = ref<'fr' | 'both'>('both')
const showEn = computed(() => langView.value === 'both')
const langItems = [{ label: 'Français', value: 'fr' }, { label: '+ English', value: 'both' }]

// Captions (the latest exchange, large) or Read instead (the whole call).
const reading = ref(false)

const caption = computed(() => {
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
  if (call.value?.handoff && !turns.value.length) return { kind: 'siu' as const, text: 'Not asked about recording' }
  return { kind: 'siu' as const, text: 'Waiting for consent' }
})
// A call handed to a person before the caller agreed to recording, where everyone must agree: nothing was kept, so
// the person picking it up reads the hand-off summary instead of an empty conversation.
const heldText = computed(() => {
  const where = /\(([^)]+)\)/.exec(call.value?.consent.ruleLabel ?? '')?.[1]
  return `${callerFirst.value} needed help before being asked about recording, and ${where ? `in ${where} ` : ''}everyone must agree first, so nothing from the call is kept. Here is what ClaimVoice handed over.`
})
const heldBack = computed(() => !!call.value?.handoff && !turns.value.length && call.value.consent.rule === 'all_party' && call.value.consent.answer !== 'given' && status.value !== 'loading')
const actionsTaken = computed(() => {
  const a = call.value?.handoff?.actionsTaken ?? []
  return a.length ? `ClaimVoice ${a.map(x => x.charAt(0).toLowerCase() + x.slice(1)).join('; ')}.` : null
})

// This line as the key bank knows it, for Listen, Take over and Hand off.
const asLine = computed(() => {
  if (line.value) return listening.fromLine(line.value)
  const c = call.value
  return c ? listening.fromLine({ callId: c.id, lineLabel: c.lineLabel ?? 'Line', callerLabel: c.callerLabel, place: c.place ?? null, language: c.language, answeredAt: c.startedAt }) : null
})
const lamp = computed<Lamp>(() => {
  const l = line.value
  const c = call.value
  if (myTake.value || c?.listeners.some(x => x.mode === 'took_over') || l?.state === 'with_person') return 'person'
  if (l?.state === 'waiting_for_person' || c?.handoff?.state === 'waiting') {
    return l?.flags.some(f => f.kind === 'urgent_safety') || c?.handoff?.priority === 'urgent' ? 'urgent' : 'waiting'
  }
  return 'line'
})
const lampWord = computed(() => {
  if (ended.value) return 'Call ended'
  if (myTake.value) return 'You\'re on the call'
  if (isOn.value) return 'You\'re listening'
  if (lamp.value === 'person') {
    const who = call.value?.listeners.find(x => x.mode === 'took_over')?.name
    return who ? `${firstName(who)} has it` : 'With a person'
  }
  if (lamp.value === 'urgent' || lamp.value === 'waiting') return call.value?.handoff?.reasonLabel ?? 'Waiting for a person'
  return 'ClaimVoice on it'
})

// Auto-listen: opening a live line lights its key in the key bank.
let autoListened = ''
watch([call, line], ([c, l]) => {
  if (!c || !l || autoListened === c.id) return
  autoListened = c.id
  if (c.state !== 'ended' && can('calls:listen') && listening.onLine.value?.callId !== c.id) void listening.listen(l)
})

// The tape's captions: the latest turn on Larkspur's side above the line (or a whisper, cobalt, until ClaimVoice's
// next turn uses it), the caller's latest turn below it, with interim words settling while they're still speaking.
function lastWhere(pred: (t: Turn) => boolean): Turn | null {
  for (let i = turns.value.length - 1; i >= 0; i--) if (pred(turns.value[i]!)) return turns.value[i]!
  return null
}
const lastLine = computed(() => lastWhere(t => t.speaker === 'line' || t.speaker === 'person'))
const freshWhisper = computed(() => {
  const w = lastWhere(t => t.speaker === 'whisper')
  return w && (!lastLine.value || w.seq > lastLine.value.seq) ? w : null
})
const waveSource: LevelSource = { who: () => (ended.value ? 'gap' : partial.value ? 'caller' : null) }

// Read: the whole call as bubbles, in a scrolling well that follows the newest turn while you're at its end.
// Captions: only the latest exchange, large.
const readEl = ref<HTMLElement | null>(null)
const behavior = (): ScrollBehavior => (prefs.reduceMotion.value ? 'auto' : 'smooth')
function toEnd(smooth = false) {
  nextTick(() => { const el = readEl.value; if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? behavior() : 'auto' }) })
}
watch(reading, (open) => { if (open) setTimeout(() => toEnd(), 60) })
let atEnd = true
watch(() => [turns.value.length, partial.value], () => {
  const el = readEl.value
  atEnd = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 80
}, { flush: 'pre' })
watch(() => [turns.value.length, partial.value], () => { if (reading.value && atEnd) toEnd(true) })
const captionTurns = computed(() => {
  const said = turns.value.filter(t => t.speaker !== 'system' && t.speaker !== 'whisper').slice(-4)
  return [...said, ...(freshWhisper.value ? [freshWhisper.value] : [])].sort((a, b) => a.seq - b.seq)
})

// A value on the notice: its words flash (LossNotice does that); with the conversation open, it scrolls to them.
function onActivate(s: Slot) {
  const key = linkKey(s.span)
  if (!reading.value || !key) return
  nextTick(() => readEl.value?.querySelector(`[data-span="${CSS.escape(key)}"]`)?.scrollIntoView({ block: 'center', behavior: behavior() }))
}
// A heard phrase in the words: its notice box lights and comes into view.
function onSpan(turnId: string, key: string) {
  const s = slotByKey(state.value.file, key)
  links.flash(s?.span ?? { turnId, start: 0, end: 0 }, false)
  nextTick(() => document.querySelector('.sheet .kv.linked')?.scrollIntoView({ block: 'nearest', behavior: behavior() }))
}

const sections = computed(() => buildNotice(state.value.file, call.value?.stage.step ?? 1, ended.value))

// Whisper / say
const text = ref('')
const sendErr = ref<string | null>(null)
const inputEl = ref<{ inputRef?: HTMLInputElement | null } | null>(null)
const focusInput = () => inputEl.value?.inputRef?.focus()
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
// ?whisper=1 (the board's Whisper): focus the input as soon as it's there.
const wantFocus = ref(route.query.whisper === '1')
watch(() => route.query.whisper, (v) => { if (v === '1') wantFocus.value = true })
watch([wantFocus, inputEl], async () => {
  if (!wantFocus.value || !inputEl.value) return
  await nextTick()
  focusInput()
  wantFocus.value = false
}, { immediate: true })

function takeOver() { if (asLine.value) listening.takeoverFor.value = asLine.value }
function handOff() { if (asLine.value) listening.handoffFor.value = asLine.value }
function toggleListen() { if (asLine.value) void listening.toggle(asLine.value) }

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable)) return
  if (e.metaKey || e.ctrlKey || e.altKey || !call.value || !line.value) return
  const k = e.key.toLowerCase()
  if (k === 'l' && can('calls:listen')) void listening.toggle(line.value)
  else if (k === 'w' && can('calls:whisper')) { e.preventDefault(); focusInput() }
  else if (k === 't' && can('calls:takeover')) listening.takeoverFor.value = listening.fromLine(line.value)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="live">
    <PageHead :title="call?.callerLabel ?? 'On the line'" :back="{ to: '/lines', label: 'Lines' }">
      <template #caption>
        {{ caption }}<template v-if="call && !ended">
          · <time class="num">{{ clock.elapsed(call.startedAt) }}</time> on the line
        </template><template v-else-if="ended">
          · the call has ended
        </template>
      </template>
      <CvTag v-if="consent" :kind="consent.kind" icon="i-lucide-shield-check" :title="call?.consent.ruleLabel">
        <span class="ct">{{ consent.text }}</span>
      </CvTag>
      <UTabs v-if="fr" v-model="langView" :items="langItems" :content="false" size="sm" color="neutral" class="hide-phone" aria-label="Transcript language" />
    </PageHead>

    <div class="room">
      <!-- The in-call stage -->
      <aside class="stage" aria-label="The call">
        <div class="ringwrap">
          <StepRing
            v-if="call" :stage="call.stage" :initials="initials(call.callerLabel)" :label="call.callerLabel" :size="148"
            :tone="lamp === 'urgent' ? 'urgent' : lamp === 'waiting' ? 'siu' : lamp === 'person' ? 'person' : 'jade'"
          />
          <USkeleton v-else class="size-[148px] rounded-full" />
        </div>
        <p class="lword" :class="`l-${ended ? 'ended' : isOn ? 'on' : lamp}`">
          <UIcon :name="ended ? 'i-lucide-check' : isOn ? 'i-lucide-headphones' : LAMP_GLYPH[lamp]" class="size-4" />{{ lampWord }}
        </p>
        <p v-if="call" class="stepw">
          Step {{ call.stage.step }} of {{ call.stage.steps }} · {{ call.stage.stepLabel }}
        </p>
        <div v-if="call && !ended" class="lvl">
          <LiveWave :seed-key="call?.id ?? id" :source="waveSource" :label="`${call.callerLabel}'s call, live`" />
        </div>

        <div class="calls" role="group" aria-label="Call controls">
          <template v-if="call && !ended">
            <RoundButton v-if="can('calls:listen')" icon="i-lucide-headphones" :label="isOn ? 'Listening' : 'Listen'" :pressed="isOn" size="lg" @click="toggleListen" />
            <RoundButton v-if="can('calls:whisper') && !myTake" icon="i-lucide-message-circle-more" label="Whisper" size="lg" @click="focusInput" />
            <RoundButton v-if="myTake" icon="i-lucide-arrow-left-right" label="Hand back" tone="person" size="lg" @click="listening.giveBack(id)" />
            <RoundButton v-else-if="can('calls:takeover')" icon="i-lucide-phone" label="Take over" size="lg" :disabled="lamp === 'person'" @click="takeOver" />
            <RoundButton v-if="can('calls:handoff')" icon="i-lucide-user-round-plus" label="Hand off" size="lg" @click="handOff" />
          </template>
          <RoundButton :icon="reading ? 'i-lucide-captions' : 'i-lucide-text'" :label="reading ? 'Captions' : 'Read instead'" size="lg" @click="reading = !reading" />
        </div>
        <p v-if="call && !ended" class="watch">
          <UIcon name="i-lucide-shield-alert" class="size-4" /><span>Listening for <b>injury, gas, water near power and distress</b></span>
        </p>
      </aside>

      <!-- The conversation -->
      <section class="talk" aria-labelledby="talk-h">
        <h2 id="talk-h" class="pool-h">
          {{ reading ? 'The whole call' : 'Said just now' }}
          <span v-if="hushCount" class="hc"><UIcon name="i-lucide-lock" class="size-3.5" />{{ hushCount }} moment{{ hushCount > 1 ? 's' : '' }} removed</span>
        </h2>

        <div class="notes">
          <StateNote v-if="status === 'lost'" kind="error" title="We lost the connection to this line." body="The call carries on; ClaimVoice keeps taking it. Reconnecting…" retry @retry="reload" />
          <StateNote v-if="error" kind="error" title="We couldn't open this line." :body="error" retry @retry="reload" />
          <UAlert v-if="heldBack && call?.handoff" color="warning" variant="soft" icon="i-lucide-shield-check" :title="heldText">
            <template #description>
              <p class="sumtext">
                {{ call.handoff.summary }}
              </p>
              <p v-if="actionsTaken" class="did">
                {{ actionsTaken }}
              </p>
            </template>
          </UAlert>
          <UAlert v-if="!retained" color="neutral" variant="soft" icon="i-lucide-shield-check" :title="notice ?? 'Recording stopped at the caller\'s request. Notes only from here.'" />
          <UAlert
            v-if="myTake && !ended" role="status" color="info" variant="soft" icon="i-lucide-phone"
            :title="`You're on the call with ${callerFirst}. Type below and the line says it; ClaimVoice is taking notes.`"
          />
          <p v-else-if="isOn && !ended" class="capnote">
            <UIcon name="i-lucide-captions" class="size-4" />You're following by live captions. The desk shows the words, not the call's audio.
          </p>
        </div>

        <div v-if="status === 'loading' && !turns.length" class="grid gap-3">
          <USkeleton class="h-16 w-3/5 rounded-[22px]" /><USkeleton class="h-16 w-1/2 rounded-[22px] justify-self-end" />
        </div>
        <div v-else-if="reading" ref="readEl" class="well" tabindex="0" aria-label="The whole call, scrollable">
          <Conversation
            :turns="turns" :marks="marks" :caller-label="call?.callerLabel" :show-en="fr && showEn"
            :interim="partial && !ended ? partial : null" :interim-at="clock.elapsed(call?.startedAt)" :lang="lang" label="The whole call" @span="onSpan"
          >
            <template v-if="ended" #after>
              <li class="endnote">
                <UIcon name="i-lucide-check" class="size-4" />The call has ended.<template v-if="call?.claimNumber">
                  Claim {{ call.claimNumber }} is filed.
                </template>
              </li>
            </template>
          </Conversation>
        </div>
        <div v-else aria-live="polite">
          <Conversation
            :turns="captionTurns" :marks="marks" :caller-label="call?.callerLabel" :show-en="fr && showEn" big
            :interim="partial && !ended ? partial : null" :lang="lang" label="Said just now" @span="onSpan"
          />
          <p v-if="!captionTurns.length && !partial && status !== 'loading'" class="empty">
            Nothing said yet.
          </p>
        </div>

        <form v-if="call && !ended && (can('calls:whisper') || myTake)" class="say" :class="{ take: myTake }" @submit.prevent="send">
          <UInput
            id="line-input" ref="inputEl" v-model="text" maxlength="280" autocomplete="off" size="xl" class="flex-1"
            :icon="myTake ? 'i-lucide-phone' : 'i-lucide-message-circle-more'"
            :aria-label="myTake ? 'Say to the caller' : 'Whisper to ClaimVoice'"
            :placeholder="myTake ? `Type what to say to ${callerFirst}. The line says it in its voice.` : `Whisper to ClaimVoice${fr ? ' in English or French' : ''}. ${callerFirst} won't hear it.`"
          />
          <UButton type="submit" size="xl" :color="myTake ? 'info' : 'primary'" :icon="myTake ? 'i-lucide-volume-2' : 'i-lucide-send'" :disabled="!text.trim()">
            {{ myTake ? 'Say it' : 'Send' }}
          </UButton>
        </form>
        <p v-if="sendErr" class="senderr" role="alert">
          <UIcon name="i-lucide-triangle-alert" class="size-4" />{{ sendErr }}
        </p>
      </section>
    </div>

    <AnswerSheet
      class="answers" title="Claim file" :sections="sections" :step="call?.stage.step ?? 1" :ended="ended" :language="call?.language ?? 'en'"
      :loading="!state.file && status === 'loading'" :reference="call?.claimNumber ? (ended ? call.claimNumber : `Draft ${call.claimNumber}`) : null"
      @activate="onActivate"
    >
      <template #head>
        <CvTag v-if="ended" kind="fast" icon="check">
          Filed
        </CvTag>
        <CvTag v-else-if="call" kind="jade">
          <span class="live-dot" aria-hidden="true" />Filling in
        </CvTag>
        <span v-if="fr" class="kept"><UIcon name="i-lucide-languages" class="size-4" />Kept in French (Law 25), English shown for staff</span>
      </template>
      <template #after>
        <EndRoute v-if="ended && call?.claimId" :claim-id="call.claimId" />
      </template>
    </AnswerSheet>

    <p class="sr-only-cv">
      Times are minutes into the call. Clock: {{ zoneLabel(line?.region) }}.
    </p>
  </div>
</template>

<style scoped>
.ct { white-space: nowrap; }
.room { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 28px; align-items: start; }

/* The in-call stage: a tall rounded handset card, sticky while the conversation scrolls. */
.stage {
  position: sticky; top: 16px; display: grid; justify-items: center; gap: 12px; padding: 28px 22px 24px; border-radius: 36px; text-align: center;
  background: linear-gradient(180deg, var(--cv-jade-wash) 0%, var(--cv-surface) 62%); box-shadow: var(--cv-shadow-soft);
}
.ringwrap { padding: 4px; }
.lword { margin: 0; display: inline-flex; align-items: center; gap: 7px; padding: 6px 14px; border-radius: 999px; font-weight: 600; font-size: 14px; background: var(--cv-surface); color: var(--cv-jade-ink); }
.l-urgent { background: var(--cv-urgent); color: #fff; }
.l-waiting { background: var(--cv-siu-wash); color: var(--cv-siu); }
.l-person { background: var(--cv-person-wash); color: var(--cv-person); }
.l-on { background: var(--cv-jade); color: var(--cv-on-jade); }
.l-ended { background: var(--cv-sunk); color: var(--cv-ink); }
[data-theme="dark"] .l-urgent { color: var(--cv-bg); }
.stepw { margin: 0; color: var(--cv-muted); font-size: 13.5px; }
.lvl { width: 100%; height: 40px; }
.calls { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px 6px; width: 100%; margin-top: 6px; justify-items: center; }
.watch { margin: 6px 0 0; display: flex; gap: 8px; align-items: flex-start; text-align: left; font-size: 13px; color: var(--cv-muted); padding: 10px 12px; border-radius: 18px; background: var(--cv-bg); }
.watch .size-4 { color: var(--cv-urgent); flex: none; margin-top: 1px; }
.watch b { color: var(--cv-ink); font-weight: 600; }

/* The conversation */
.talk { display: grid; gap: 16px; min-width: 0; }
.hc { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; padding: 3px 11px; border-radius: 999px; background: var(--cv-sunk); color: var(--cv-muted); font-family: var(--font-sans); font-size: 12.5px; font-weight: 500; letter-spacing: 0; }
.notes { display: grid; gap: 8px; }
.notes:empty { display: none; }
.capnote { margin: 0; display: flex; gap: 8px; align-items: center; color: var(--cv-muted); font-size: 13.5px; }
.sumtext { white-space: pre-line; font-size: 15px; line-height: 1.45; margin: 4px 0 0; color: var(--cv-ink); }
.did { margin: 4px 0 0; font-size: 13.5px; }
.well { max-height: min(62vh, 640px); overflow-y: auto; padding: 16px; border-radius: 28px; background: var(--cv-surface); box-shadow: inset 0 0 0 2px var(--cv-sunk); scrollbar-width: thin; }
.empty { margin: 0; color: var(--cv-muted); }
.endnote { justify-self: center; list-style: none; display: flex; gap: 6px; align-items: center; padding: 6px 14px; border-radius: 999px; background: var(--cv-jade-wash); color: var(--cv-jade-ink); font-weight: 500; font-size: 14px; }
.say { display: flex; gap: 8px; align-items: center; padding: 8px; border-radius: 24px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.say.take { box-shadow: 0 0 0 3px var(--cv-person), var(--cv-shadow-soft); }
.say :deep(input) { box-shadow: none; --tw-ring-color: transparent; }
.senderr { margin: 0; display: flex; gap: 6px; align-items: center; color: var(--cv-urgent); font-size: 13.5px; font-weight: 500; }
.kept { display: inline-flex; align-items: center; gap: 6px; color: var(--cv-muted); font-size: 13.5px; }
.answers { margin-top: 44px; }

@media (max-width: 1100px) {
  .room { grid-template-columns: minmax(0, 1fr); }
  .stage { position: static; grid-template-columns: auto minmax(0, 1fr); justify-items: start; text-align: left; align-items: center; }
  .ringwrap { grid-row: span 3; }
  .calls, .lvl, .watch { grid-column: 1 / -1; }
  .calls { grid-template-columns: repeat(auto-fill, minmax(76px, 1fr)); }
}
@media (max-width: 720px) {
  .ct { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .stage { padding: 18px 14px; border-radius: 28px; gap: 8px 14px; }
  .stage :deep(.sring) { width: 96px !important; height: 96px !important; }
  .calls { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .say { flex-wrap: wrap; }
  .say :deep(.flex-1) { flex-basis: 100%; }
  .answers { margin-top: 32px; }
}
</style>
