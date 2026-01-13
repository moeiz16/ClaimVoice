<script setup lang="ts">
// The live call (DESIGN.md §5.2): the slate (caller, line, place, loss, elapsed; recording consent, transcript
// language, Captions / Read instead), then the tape: the line's key and the talkback keys at its left, the live
// two-voice line with ClaimVoice's (or the person's) latest turn written above it and the caller's below, interim
// words settling, and the whisper / say input at its foot. Under it the loss notice fills in, section by section;
// when the call ends the route sits on it as section 8. "Read instead" opens the whole conversation from the left.
// Keyboard: L listen, W whisper, T take over. ?whisper=1 opens with the whisper input focused.
import type { LevelSource } from '~/composables/useLiveLevels'
import type { Slot, Turn } from '~/types/api'
import { linkKey } from '~/composables/useHeardLinks'
import { api } from '~/utils/api'
import { LAMP_GLYPH, lineNumber } from '~/utils/board'
import type { Lamp } from '~/utils/board'
import { firstName, fmtClock, zoneLabel } from '~/utils/format'
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
const reduced = useReducedMotionPref()
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
const whoName = (t: Turn) => (t.speaker === 'caller' ? firstName(/^(caller|appelant)$/i.test(t.speakerLabel) ? (call.value?.callerLabel ?? t.speakerLabel) : t.speakerLabel) : t.speakerLabel)

// Transcript language: French calls show the French first, with an English line under each turn for staff.
const langView = ref<'fr' | 'both'>('both')
const showEn = computed(() => langView.value === 'both')
const langItems = [{ label: 'Français', value: 'fr' }, { label: '+ English', value: 'both' }]

// Captions on the tape, or the whole conversation from the left.
const reading = ref(false)
const follow = computed({ get: () => (reading.value ? 'read' : 'captions'), set: (v: string) => { reading.value = v === 'read' } })
const followItems = [{ label: 'Captions', value: 'captions', icon: 'i-lucide-captions' }, { label: 'Read instead', value: 'read', icon: 'i-lucide-text' }]

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
const lineNo = computed(() => lineNumber(call.value?.lineLabel ?? line.value?.lineLabel))
const lineLabel = computed(() => call.value?.lineLabel ?? line.value?.lineLabel ?? 'Line')
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
const lastCaller = computed(() => lastWhere(t => t.speaker === 'caller'))
const freshWhisper = computed(() => {
  const w = lastWhere(t => t.speaker === 'whisper')
  return w && (!lastLine.value || w.seq > lastLine.value.seq) ? w : null
})
const whisperBy = (t: Turn) => t.speakerLabel.split('·')[1]?.trim() ?? ''
const waveSource: LevelSource = { who: () => (ended.value ? 'gap' : partial.value ? 'caller' : null) }

// Ripple from the line key at each new turn.
const ripple = ref(0)
watch(() => turns.value.length, (n, o) => { if (o !== undefined && n > o && !reduced.value) ripple.value++ })

// Read instead: the whole conversation in a slide-over from the left, beside the notice. It follows the newest turn
// while you're at the end of it.
const readEl = ref<HTMLElement | null>(null)
const keepOpen = { onInteractOutside: (e: Event) => e.preventDefault() }
const behavior = (): ScrollBehavior => (prefs.reduceMotion.value ? 'auto' : 'smooth')
function toEnd(smooth = false) {
  nextTick(() => readEl.value?.lastElementChild?.scrollIntoView({ block: 'end', behavior: smooth ? behavior() : 'auto' }))
}
watch(reading, (open) => { if (open) setTimeout(() => toEnd(), 60) })
let atEnd = true
watch(() => [turns.value.length, partial.value], () => {
  const last = readEl.value?.lastElementChild
  atEnd = !last || last.getBoundingClientRect().top < window.innerHeight
}, { flush: 'pre' })
watch(() => [turns.value.length, partial.value], () => { if (reading.value && atEnd) toEnd(true) })

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
  nextTick(() => document.querySelector('.notice .box.linked')?.scrollIntoView({ block: 'nearest', behavior: behavior() }))
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
    <Slate :title="call?.callerLabel ?? 'On the line'" :back="{ to: '/lines', label: 'Board' }">
      <template #caption>
        {{ caption }}<template v-if="call && !ended">
          · <time class="num">{{ clock.elapsed(call.startedAt) }}</time>
        </template><template v-else-if="ended">
          · ended
        </template>
      </template>
      <CvTag v-if="consent" :kind="consent.kind" icon="i-lucide-shield-check" :title="call?.consent.ruleLabel">
        <span class="ct">{{ consent.text }}</span>
      </CvTag>
      <UTabs v-if="fr" v-model="langView" :items="langItems" :content="false" variant="pill" size="sm" color="neutral" class="hide-phone" aria-label="Transcript language" />
      <UTabs v-model="follow" :items="followItems" :content="false" variant="pill" size="sm" color="neutral" aria-label="How to follow the call" />
    </Slate>

    <Tape :label="`${call?.callerLabel ?? 'The'} call, live`">
      <template #key>
        <div class="keyrow">
          <div class="lkey" :class="[`lamp-${lamp}`, { on: isOn && !ended, ended }]" role="img" :aria-label="`${lineLabel}, ${lampWord}`">
            <span class="n num">{{ lineNo ?? '·' }}</span>
            <span class="lamp" aria-hidden="true">
              <UIcon v-if="ended" name="i-lucide-check" class="size-3.5" />
              <UIcon v-else-if="isOn" name="i-lucide-headphones" class="size-3.5" />
              <UIcon v-else :name="LAMP_GLYPH[lamp]" class="size-3.5" />
            </span>
            <span v-if="ripple" :key="ripple" class="ripple-ring" aria-hidden="true" />
          </div>
          <span class="lword">{{ lampWord }}</span>
        </div>
        <div v-if="call && !ended" class="talk" role="group" aria-label="Talkback">
          <UButton
            v-if="can('calls:listen')" size="md" :color="isOn ? 'primary' : 'neutral'" :variant="isOn ? 'solid' : 'soft'"
            icon="i-lucide-headphones" :aria-pressed="isOn" @click="toggleListen"
          >
            {{ isOn ? 'Listening' : 'Listen' }}
          </UButton>
          <UButton v-if="can('calls:whisper') && !myTake" size="md" color="neutral" variant="soft" icon="i-lucide-message-square-more" @click="focusInput">
            Whisper
          </UButton>
          <UButton v-if="myTake" size="md" color="info" icon="i-lucide-arrow-left-right" @click="listening.giveBack(id)">
            Hand back
          </UButton>
          <UButton v-else-if="can('calls:takeover')" size="md" color="neutral" icon="i-lucide-phone" :disabled="lamp === 'person'" @click="takeOver">
            Take over
          </UButton>
          <UButton v-if="can('calls:handoff')" size="md" color="neutral" variant="soft" icon="i-lucide-user-round-plus" @click="handOff">
            Hand off
          </UButton>
        </div>
      </template>

      <template #above>
        <div aria-live="polite" class="capwrap">
          <Transition name="cap" mode="out-in">
            <div v-if="freshWhisper" :key="freshWhisper.id" class="cap whisper">
              <small class="who"><UIcon name="i-lucide-message-square-more" class="size-3.5" />Whisper, ClaimVoice only{{ whisperBy(freshWhisper) ? ` · ${whisperBy(freshWhisper)}` : '' }}</small>
              <p>{{ freshWhisper.text }}</p>
            </div>
            <div v-else-if="lastLine" :key="lastLine.id" class="cap" :class="[lastLine.speaker, { interrupted: lastLine.interrupted }]">
              <small class="who"><i aria-hidden="true" />{{ whoName(lastLine) }}</small>
              <p :lang="lastLine.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="lastLine.text" :turn-id="lastLine.id" :marks="marks[lastLine.id]" @span="k => onSpan(lastLine!.id, k)" />
              </p>
              <span v-if="lastLine.textEn && fr && showEn" class="tr">{{ lastLine.textEn }}</span>
            </div>
            <div v-else-if="status === 'loading'" key="loading" class="cap">
              <USkeleton class="h-3 w-24 mb-2" /><USkeleton class="h-7 w-3/5" />
            </div>
          </Transition>
        </div>
      </template>

      <LiveWave :seed-key="call?.id ?? id" :source="waveSource" />

      <template #below>
        <div aria-live="polite" class="capwrap">
          <Transition name="cap" mode="out-in">
            <div v-if="partial && !ended" key="interim" class="cap caller" aria-hidden="true">
              <small class="who"><i />{{ callerFirst }} <span class="hearing">hearing now</span></small>
              <p :lang="lang">
                <span v-for="(w, i) in partial.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ `${w} ` }}</span>
              </p>
            </div>
            <div v-else-if="lastCaller" :key="lastCaller.id" class="cap caller" :class="{ interrupted: lastCaller.interrupted }">
              <small class="who"><i aria-hidden="true" />{{ whoName(lastCaller) }}</small>
              <p :lang="lastCaller.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="lastCaller.text" :turn-id="lastCaller.id" :marks="marks[lastCaller.id]" @span="k => onSpan(lastCaller!.id, k)" />
              </p>
              <span v-if="lastCaller.textEn && fr && showEn" class="tr">{{ lastCaller.textEn }}</span>
            </div>
          </Transition>
        </div>
      </template>

      <template #foot>
        <form v-if="call && !ended && (can('calls:whisper') || myTake)" class="say" @submit.prevent="send">
          <UInput
            id="line-input" ref="inputEl" v-model="text" maxlength="280" autocomplete="off" size="xl" class="flex-1"
            :color="myTake ? 'info' : 'neutral'" :highlight="myTake"
            :icon="myTake ? 'i-lucide-phone' : 'i-lucide-message-square-more'"
            :aria-label="myTake ? 'Say to the caller' : 'Whisper to ClaimVoice'"
            :placeholder="myTake ? `Type what to say to ${callerFirst}. It's spoken in the line's voice.` : `Whisper to ClaimVoice${fr ? ' in English or French' : ''}. ${callerFirst} won't hear this.`"
          />
          <UButton type="submit" size="xl" :color="myTake ? 'info' : 'neutral'" :variant="myTake ? 'solid' : 'soft'" :icon="myTake ? 'i-lucide-volume-2' : 'i-lucide-send'" :disabled="!text.trim()">
            {{ myTake ? 'Say it' : 'Send' }}
          </UButton>
        </form>
        <p v-if="sendErr" class="senderr" role="alert">
          <UIcon name="i-lucide-triangle-alert" class="size-4" />{{ sendErr }}
        </p>
        <p v-if="call && !ended" class="watch">
          <UIcon name="i-lucide-triangle-alert" class="size-4" />Listening for <b>injury · gas · water near power · distress</b>
        </p>
      </template>
    </Tape>

    <div v-if="status === 'lost' || error || !retained || myTake || heldBack || (isOn && !myTake && !ended) || ended" class="notes">
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
        :actions="[{ label: 'Hand back to ClaimVoice', icon: 'i-lucide-arrow-left-right', color: 'info', variant: 'outline', size: 'md', onClick: () => listening.giveBack(id) }]"
      />
      <UAlert
        v-else-if="isOn && !ended" color="neutral" variant="subtle" icon="i-lucide-captions"
        title="You're following this call by live captions. The desk shows the words, not the call's audio."
      />
      <UAlert v-if="ended" role="status" color="success" variant="soft" icon="i-lucide-check" :title="`The call has ended.${call?.claimNumber ? ` Claim ${call.claimNumber} is filed.` : ''}`" />
    </div>

    <LossNotice
      title="Claim file" :sections="sections" :step="call?.stage.step ?? 1" :ended="ended" :turns="turns" :language="call?.language ?? 'en'"
      :loading="!state.file && status === 'loading'" :reference="call?.claimNumber ? (ended ? call.claimNumber : `Draft ${call.claimNumber}`) : null"
      @activate="onActivate"
    >
      <template #head>
        <CvTag v-if="ended" kind="fast" icon="check">
          Filed
        </CvTag>
        <CvTag v-else-if="call" kind="orchid">
          <span class="live-dot" aria-hidden="true" />Filling in
        </CvTag>
        <span v-if="fr" class="kept"><UIcon name="i-lucide-languages" class="size-4" />Kept in French (Law 25), English shown for staff</span>
      </template>
      <template #after>
        <EndRoute v-if="ended && call?.claimId" :claim-id="call.claimId" />
      </template>
    </LossNotice>

    <USlideover
      v-model:open="reading" side="left" :modal="false" :overlay="false" :content="keepOpen"
      :title="`Conversation${fr ? ' · heard in French' : ''}`"
      :ui="{ content: 'max-w-[min(760px,100vw)]', body: 'p-0 sm:p-0' }"
    >
      <template #description>
        <span class="rdesc">
          <CvTag icon="lock">{{ hushCount ? `${hushCount} moment${hushCount > 1 ? 's' : ''} removed` : 'Nothing removed' }}</CvTag>
          <span>Times are minutes into the call.</span>
        </span>
      </template>
      <template #body>
        <ol ref="readEl" class="rows" aria-label="The whole conversation">
          <li v-if="heldBack && call?.handoff" class="row held">
            <span />
            <div>
              <p class="note">
                <UIcon name="i-lucide-shield-check" class="size-4" />{{ heldText }}
              </p>
              <p class="sumtext">
                {{ call.handoff.summary }}
              </p>
              <p v-if="actionsTaken" class="sys">
                {{ actionsTaken }}
              </p>
            </div>
          </li>
          <li v-if="!retained" class="row">
            <span />
            <p class="note">
              <UIcon name="i-lucide-shield-check" class="size-4" />{{ notice ?? 'Recording stopped at the caller\'s request. Notes only from here.' }}
            </p>
          </li>
          <template v-if="status === 'loading'">
            <li v-for="n in 3" :key="`sk-${n}`" class="row">
              <span /><div><USkeleton class="h-3 w-1/4 mb-2" /><USkeleton class="h-5 w-11/12" /></div>
            </li>
          </template>
          <li v-for="t in turns" :key="t.id" class="row" :class="[t.speaker, { interrupted: t.interrupted }]">
            <time class="num">{{ at(t) }}</time>
            <div>
              <div class="who">
                <i aria-hidden="true" />{{ t.speaker === 'whisper' ? 'Whisper, ClaimVoice only' : whoName(t) }}
              </div>
              <p v-if="t.speaker === 'whisper'" class="whisper-p">
                <UIcon name="i-lucide-message-square-more" class="size-4" />{{ whisperBy(t) }}{{ whisperBy(t) ? ': ' : '' }}{{ t.text }}
              </p>
              <p v-else-if="t.speaker === 'system'" class="sys">
                {{ t.text }}
              </p>
              <p v-else :lang="t.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="t.text" :turn-id="t.id" :marks="marks[t.id]" @span="k => onSpan(t.id, k)" />
              </p>
              <span v-if="t.textEn && fr && showEn" class="tr">{{ t.textEn }}</span>
            </div>
          </li>
          <li v-if="partial && !ended" class="row caller" aria-hidden="true">
            <time class="num">{{ clock.elapsed(call?.startedAt) }}</time>
            <div>
              <div class="who">
                <i />{{ callerFirst }} <span class="hearing">hearing now</span>
              </div>
              <p :lang="lang">
                <span v-for="(w, i) in partial.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ `${w} ` }}</span>
              </p>
            </div>
          </li>
          <li v-if="ended" class="row end">
            <span />
            <p>
              <UIcon name="i-lucide-check" class="size-4 text-fast" />The call has ended.<template v-if="call?.claimNumber">
                Claim {{ call.claimNumber }} is filed.
              </template>
            </p>
          </li>
        </ol>
      </template>
    </USlideover>

    <p class="sr-only-cv">
      Times are minutes into the call. Clock: {{ zoneLabel(line?.region) }}.
    </p>
  </div>
</template>

<style scoped>
.live { padding-bottom: 32px; }
.ct { white-space: nowrap; }

/* The tape's key column: the line's key (as on the board) with its lamp and word, then the talkback keys. */
.keyrow { display: flex; align-items: center; gap: 10px; }
.lkey {
  position: relative; flex: none; width: 60px; height: 56px; border-radius: 10px; display: grid; place-items: center; align-content: center; gap: 2px;
  background: var(--cv-dock); color: var(--cv-on-dock); box-shadow: inset 0 -2px 0 rgba(0, 0, 0, .3);
}
.lkey .n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 21px; font-weight: 720; line-height: 1; }
.lamp { width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; background: color-mix(in srgb, var(--cv-dock-orchid) 30%, transparent); color: var(--cv-dock-orchid); }
.lamp-waiting .lamp { background: #F2C36B; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-urgent { box-shadow: inset 0 0 0 2px #FF8070; }
.lamp-urgent .lamp { background: #FF8070; color: #2A1530; animation: lamp 1s steps(1, end) infinite; }
.lamp-person .lamp { background: #8FAEFF; color: #1F2747; }
.lkey.on .lamp { background: var(--cv-dock-orchid); color: #2A1530; animation: none; }
.lkey.ended .lamp { background: color-mix(in srgb, var(--cv-on-dock) 18%, transparent); color: var(--cv-on-dock); animation: none; }
.lkey .ripple-ring { border-radius: 10px; }
.lword { font-size: 13px; font-weight: 650; color: var(--cv-muted); line-height: 1.25; }
.talk { display: grid; gap: 6px; }
.talk :deep(button) { justify-content: flex-start; }

/* Captions written on the tape. */
.capwrap { min-height: 1.22em; }
.cap p { margin: 0; }
.cap .who {
  display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
  font-family: var(--font-sans); font-variation-settings: normal; font-size: 12.5px; font-weight: 650; letter-spacing: 0; color: var(--cv-muted); line-height: 1.3;
}
.cap .who i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); }
.cap.person .who i { background: var(--cv-person); }
.cap.person p { color: var(--cv-person); }
.cap.caller .who { justify-content: flex-end; }
.cap.caller .who i { background: var(--cv-caller); }
.cap.whisper p { color: var(--cv-person); }
.cap.whisper .who { color: var(--cv-person); }
.cap .tr { display: block; font-family: var(--font-sans); font-variation-settings: normal; font-size: 14px; font-weight: 500; letter-spacing: 0; color: var(--cv-muted); margin-top: 4px; line-height: 1.4; }
.cap.interrupted p::after, .row.interrupted p::after { content: " …"; color: var(--cv-faint); }
.hearing { font-weight: 650; color: var(--cv-orchid-ink); font-size: 11.5px; }
.cap-enter-active, .cap-leave-active { transition: opacity 180ms var(--ease-voice); }
.cap-enter-from, .cap-leave-to { opacity: 0; }

/* The tape's foot: whisper or say, then the safety watch. */
.say { display: flex; gap: 8px; align-items: center; }
.senderr { margin: 8px 0 0; display: flex; gap: 6px; align-items: center; color: var(--cv-urgent); font-size: 13px; font-weight: 600; }
.watch { margin: 10px 0 0; display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--cv-muted); font-weight: 600; flex-wrap: wrap; }
.watch b { color: var(--cv-ink); }

/* State rows between the tape and the notice. */
.notes { display: grid; gap: 8px; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.sumtext { white-space: pre-line; font-size: 15px; font-weight: 550; line-height: 1.45; margin: 4px 0 0; color: var(--cv-ink); }
.did { margin: 4px 0 0; font-size: 13.5px; }
.kept { display: inline-flex; align-items: center; gap: 6px; color: var(--cv-muted); font-size: 13px; font-weight: 600; }

/* Read instead: the whole conversation, rows with a time gutter. */
.rdesc { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rows { list-style: none; margin: 0; padding: 8px 0 16px; }
.row {
  display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 10px; padding: 10px 24px 10px 16px;
  border-bottom: 1px solid var(--cv-rule); font-size: calc(15.5px * var(--cv-caption-scale)); line-height: 1.55;
}
.row time { color: var(--cv-muted); font-size: 12.5px; font-weight: 650; padding-top: 3px; text-align: right; }
.row .who { font-weight: 700; font-size: 12.5px; display: flex; align-items: center; gap: 6px; color: var(--cv-muted); }
.row .who i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); }
.row.caller .who i { background: var(--cv-caller); }
.row.person .who i, .row.whisper .who i { background: var(--cv-person); }
.row.system .who i { background: var(--cv-faint); }
.row.caller p { color: var(--cv-caller); }
.row.person p { color: var(--cv-person); }
.row p { margin: 1px 0 0; }
.row .tr { display: block; color: var(--cv-muted); font-size: 13.5px; margin-top: 2px; }
.row.whisper { background: var(--cv-person-wash); }
.whisper-p { color: var(--cv-person); font-weight: 600; font-size: 14px; display: flex; gap: 8px; align-items: center; }
.sys { color: var(--cv-muted); font-style: italic; font-size: 14px; }
.note { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; }
.row.end p { display: flex; gap: 6px; align-items: center; font-weight: 600; }
.row.held { display: grid; }

@media (max-width: 1100px) {
  .talk { display: flex; flex-wrap: wrap; }
  .keyrow { margin-right: 6px; }
}
@media (max-width: 720px) {
  .ct { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .notes { padding: 12px 16px; }
  .say { flex-wrap: wrap; }
  .say :deep(.flex-1) { flex-basis: 100%; }
  .row { grid-template-columns: 40px minmax(0, 1fr); padding: 10px 16px 10px 8px; font-size: 15px; }
  .cap .tr { font-size: 13px; }
}
:global(:root.reduce-motion) .lamp { animation: none !important; }
@media (prefers-reduced-motion: reduce) { .lamp { animation: none !important; } }
</style>
