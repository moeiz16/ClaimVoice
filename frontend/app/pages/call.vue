<script setup lang="ts">
// Ring the demo line (DESIGN.md §4): a live call in this browser. The orb breathes while idle, reacts to the
// microphone while listening and pulses while ClaimVoice speaks; captions in two alignments (your words settle from
// faint to ink); the claim slip fills; the route unfurls at the end. ?type opens the typed call; ?lang=fr calls in
// French.
import type { CallMode, Lang } from '~/types/api'
import { fmtClock } from '~/utils/format'
import { slipIcon } from '~/utils/labels'
import type { Who } from '~/utils/waveform'

definePageMeta({ layout: 'public' })
const route = useRoute()
const prefs = usePrefs()
const call = useDemoCall()
const { state, lines, interim, stage, slip, notice, hushed, ended, muted, micLevel } = call
const lang = ref<Lang>(route.query.lang === 'fr' ? 'fr' : (prefs.lang.value === 'fr' ? 'fr' : 'en'))
const fr = computed(() => lang.value === 'fr')
const typedText = ref('')
const typedInput = ref<HTMLInputElement | null>(null)
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { timer = setInterval(() => { elapsed.value = call.startedAt.value ? Math.floor((Date.now() - call.startedAt.value) / 1000) : 0 }, 500) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
useHead(() => ({ title: fr.value ? 'Appeler la ligne de démo · ClaimVoice' : 'Ring the demo line · ClaimVoice', htmlAttrs: { lang: lang.value } }))

const T = computed(() => fr.value
  ? { title: 'Appeler la ligne de démo', lede: 'Imaginez qu\'il vient d\'arriver quelque chose à votre auto ou à votre maison.', note: 'Utilise votre micro dans ce navigateur seulement. Rien de ce que vous dites n\'est gardé après la fermeture de la page.', ring: 'Appeler la ligne de démo', type: 'Écrire plutôt', other: 'Call in English', tryLine: 'Essayez : « Quelqu\'un a reculé dans mon auto au stationnement. »', ringing: 'Ça sonne…', listening: 'À vous. Je vous écoute.', typeTurn: 'À vous. Écrivez votre réponse.', speaking: 'ClaimVoice parle', you: 'Vous', hang: 'Raccrocher', mute: 'Couper la voix', unmute: 'Activer la voix', toTyped: 'Écrire plutôt', placeholder: 'Écrivez ce que vous diriez…', send: 'Envoyer', blocked: 'Votre navigateur n\'a pas permis d\'utiliser le micro. Vous pouvez écrire plutôt.', noRec: 'Ce navigateur ne reconnaît pas la parole, alors l\'appel se fait par écrit. ClaimVoice vous répond quand même à voix haute.', busy: 'Toutes les lignes de démo sont occupées. Réessayez dans une minute.', lost: 'L\'appel a été coupé.', again: 'Rappeler', slip: 'Votre dossier', endH: 'Votre réclamation est faite.', next: 'Et ensuite', back: 'Retour à la page' }
  : { title: 'Ring the demo line', lede: 'Pretend something has just happened to your car or your home.', note: 'Uses your microphone in this browser only. Nothing you say is kept after you close the page.', ring: 'Ring the demo line', type: 'Type instead', other: 'Appeler en français', tryLine: 'Try: “Someone backed into my car in the Chinook Centre parking lot.”', ringing: 'Ringing…', listening: 'Your turn. I\'m listening.', typeTurn: 'Your turn. Type your answer.', speaking: 'ClaimVoice is speaking', you: 'You', hang: 'Hang up', mute: 'Mute the voice', unmute: 'Turn the voice on', toTyped: 'Type instead', placeholder: 'Type what you would say…', send: 'Send', blocked: 'Your browser didn\'t let us use the microphone. You can type instead.', noRec: 'This browser can\'t recognise speech, so the call is typed. ClaimVoice still answers out loud.', busy: 'All the demo lines are busy. Try again in a minute.', lost: 'The call dropped.', again: 'Ring again', slip: 'Your claim file', endH: 'Your claim is in.', next: 'What happens next', back: 'Back to the page' })

function ring(mode: CallMode, l: Lang = lang.value) {
  lang.value = l
  void call.start({ mode, lang: l })
}
onMounted(() => { if ('type' in route.query) ring('typed') })
watch(() => call.mode.value, async (m) => { if (m === 'typed') { await nextTick(); typedInput.value?.focus() } })

const live = computed(() => ['ringing', 'listening', 'speaking'].includes(state.value))
const orbState = computed(() => (state.value === 'speaking' ? 'speaking' : state.value === 'listening' ? 'listening' : state.value === 'ringing' || state.value === 'starting' ? 'ringing' : state.value === 'ended' ? 'ended' : 'idle'))
const shown = computed(() => lines.value.slice(-3))
const status = computed(() => (state.value === 'ringing' || state.value === 'starting' ? T.value.ringing : state.value === 'speaking' ? T.value.speaking : state.value === 'listening' ? (call.mode.value === 'typed' ? T.value.typeTurn : T.value.listening) : ''))
const remaining = computed(() => Math.max(0, call.maxSeconds.value - elapsed.value))
const levelSource = {
  level: (): { who: Who, level: number } | null => {
    if (state.value === 'listening' && micLevel.value > 0.04) return { who: 'caller', level: micLevel.value }
    if (state.value === 'speaking') return null
    return { who: 'gap', level: 0.03 }
  },
  who: (): Who => (state.value === 'speaking' ? 'cv' : 'gap'),
}
// The caller's slip: what was heard, each short answer with its question ("Injury reported No", not a bare "No").
// The caller's own first sentence and the next steps (shown in full at the end) are left out.
const SLIP_HIDDEN = new Set(['loss_description', 'next_steps_given', 'adjuster_contact_window', 'identity_check'])
const shownSlip = computed(() => slip.value.filter(s => !SLIP_HIDDEN.has(s.key)))
const labelled = (s: { value: unknown, display: string }) => typeof s.value === 'boolean' || typeof s.value === 'number' || /^[\d,.$ ]+$/.test(s.display)
function sendTyped() { call.sendTyped(typedText.value); typedText.value = '' }
</script>

<template>
  <div class="callpage" :class="state">
    <header class="top">
      <CvLogo />
      <div class="seg" role="group" aria-label="Language / Langue">
        <button type="button" :aria-pressed="!fr" :disabled="live" @click="lang = 'en'">
          English
        </button>
        <button type="button" :aria-pressed="fr" :disabled="live" lang="fr" @click="lang = 'fr'">
          Français
        </button>
      </div>
      <NuxtLink class="iconbtn" to="/#ring" :aria-label="T.back">
        <CvIcon name="x" />
      </NuxtLink>
    </header>

    <main class="stage">
      <div v-if="state === 'idle' || state === 'blocked' || state === 'busy' || state === 'lost'" class="intro">
        <h1>{{ T.title }}</h1>
        <p class="lede">
          {{ T.lede }}
        </p>
        <div class="orbwrap">
          <DemoOrb state="idle" />
        </div>
        <p class="try">
          {{ T.tryLine }}
        </p>
        <p v-if="state === 'blocked'" class="warn" role="alert">
          <CvIcon name="micoff" size="s" />{{ T.blocked }}
        </p>
        <p v-if="state === 'busy'" class="warn" role="alert">
          <CvIcon name="clock" size="s" />{{ T.busy }}
        </p>
        <p v-if="state === 'lost'" class="warn" role="alert">
          <CvIcon name="urgent" size="s" />{{ T.lost }} {{ call.error.value ?? '' }}
        </p>
        <div class="acts">
          <button v-if="state !== 'blocked'" class="btn primary" type="button" @click="ring('browser_speech')">
            <CvIcon name="mic" />{{ T.ring }}
          </button>
          <button class="btn soft on-sunk" :class="{ primary: state === 'blocked' }" type="button" @click="ring('typed')">
            <CvIcon name="keys" />{{ T.type }}
          </button>
          <button class="btn soft on-sunk" type="button" :lang="fr ? 'en' : 'fr'" @click="ring('browser_speech', fr ? 'en' : 'fr')">
            <CvIcon name="lang" />{{ T.other }}
          </button>
        </div>
        <p class="note">
          {{ T.note }}
        </p>
      </div>

      <div v-else class="oncall">
        <div class="orbline">
          <DemoOrb :state="orbState" :level="micLevel" :size="148" :typed="call.mode.value === 'typed'" />
          <div class="statusline" role="status">
            <span v-if="live" class="live-dot" aria-hidden="true" />{{ status }}
            <span v-if="live && call.startedAt.value" class="t num">{{ fmtClock(elapsed) }} · {{ fmtClock(remaining) }} left</span>
          </div>
          <div v-if="stage && state !== 'ended'" class="steptrack">
            <ScriptProgress :stage="stage" />
            <span>{{ fr ? 'Étape' : 'Step' }} {{ stage.step }} / {{ stage.steps }} · {{ stage.stepLabel }}</span>
          </div>
        </div>
        <div class="wave" aria-hidden="true">
          <LiveWave seed-key="demo-line" :source="levelSource" />
          <span v-if="hushed" class="tag orchid hushnote"><CvIcon name="lock" size="s" />{{ notice ?? (fr ? 'Enregistrement en pause' : 'Recording paused · card number') }}</span>
        </div>
        <p v-if="call.noRecognition.value && call.mode.value === 'typed'" class="info">
          <CvIcon name="keys" size="s" />{{ T.noRec }}
        </p>
        <section class="captions" aria-live="polite" :aria-label="fr ? 'Sous-titres' : 'Captions'">
          <div v-for="(l, i) in shown" :key="l.id" class="cap" :class="[l.who, i === shown.length - 1 && !interim ? 'now' : 'past']">
            <span class="who"><i />{{ l.who === 'cv' ? 'ClaimVoice' : T.you }}</span>
            <p>{{ l.text }}</p>
          </div>
          <div v-if="interim && state !== 'ended'" class="cap caller now" aria-hidden="true">
            <span class="who"><i />{{ T.you }}</span>
            <p><span v-for="(w, i) in interim.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ w }} </span></p>
          </div>
        </section>

        <div v-if="slip.length || ended" class="slip">
          <span class="label"><CvIcon name="doc" size="s" />{{ T.slip }}</span>
          <span v-for="s in shownSlip" :key="s.key" class="heard plain in"><span class="ic"><CvIcon :name="slipIcon(s.key)" size="s" /></span><span v-if="labelled(s)" class="k">{{ s.label }}</span>{{ s.display }}</span>
        </div>

        <section v-if="ended" class="end">
          <h2>{{ T.endH }} <span v-if="ended.claimNumber" class="num">{{ ended.claimNumber }}</span></h2>
          <div v-if="ended.route" class="routepill">
            <RouteTag :route="ended.route.route" :label="ended.route.label" />
            <ol><li v-for="(r, i) in ended.route.reasons" :key="i" :style="{ animationDelay: `${600 + i * 90}ms` }"><b>{{ i + 1 }}</b>{{ r.text }}</li></ol>
          </div>
          <div v-if="ended.nextSteps.length" class="next">
            <div class="group-label">
              {{ T.next }}
            </div>
            <ul><li v-for="n in ended.nextSteps" :key="n"><CvIcon name="check" size="s" />{{ n }}</li></ul>
          </div>
          <div class="acts">
            <button class="btn primary" type="button" @click="ring(call.mode.value)">
              <CvIcon name="phone" />{{ T.again }}
            </button>
            <NuxtLink class="btn soft on-sunk" to="/">
              {{ T.back }}
            </NuxtLink>
          </div>
        </section>

        <div v-if="state !== 'ended'" class="controls">
          <form v-if="call.mode.value === 'typed'" class="typed" @submit.prevent="sendTyped">
            <CvIcon name="keys" />
            <label class="sr-only-cv" for="typed">{{ T.placeholder }}</label>
            <input id="typed" ref="typedInput" v-model="typedText" :placeholder="T.placeholder" autocomplete="off" maxlength="400">
            <button class="btn primary sm" type="submit" :disabled="!typedText.trim()">
              {{ T.send }}
            </button>
          </form>
          <div class="btns">
            <button v-if="call.mode.value !== 'typed'" class="btn soft on-sunk sm" type="button" @click="call.switchToTyped()">
              <CvIcon name="keys" size="s" />{{ T.toTyped }}
            </button>
            <button class="btn soft on-sunk sm" type="button" :aria-pressed="muted" @click="muted = !muted">
              <CvIcon :name="muted ? 'mute' : 'volume'" size="s" />{{ muted ? T.unmute : T.mute }}
            </button>
            <button class="btn danger sm" type="button" @click="call.hangUp()">
              <CvIcon name="hangup" size="s" />{{ T.hang }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.callpage { min-height: 100dvh; background: var(--cv-orchid-wash); display: grid; grid-template-rows: 76px 1fr; }
.top { display: flex; align-items: center; gap: 14px; padding: 0 40px; }
.top .seg { margin-left: auto; }
.top .seg button { height: 36px; padding: 0 14px; font-size: 14px; }
.top .iconbtn { background: var(--cv-surface); }
.stage { display: grid; justify-items: center; padding: 0 24px 48px; }
.intro { display: grid; justify-items: center; text-align: center; max-width: 720px; padding-top: 24px; }
h1 { font-size: 54px; font-weight: 750; letter-spacing: -0.04em; }
.lede { color: var(--cv-muted); font-size: 17px; margin: 12px 0 0; }
.orbwrap { margin: 42px 0 28px; }
.try { font-family: var(--font-display); font-size: 24px; font-weight: 600; color: var(--cv-caller); margin: 0; letter-spacing: -0.02em; }
.warn { display: flex; gap: 8px; align-items: center; margin: 18px 0 0; font-weight: 650; color: var(--cv-urgent); background: var(--cv-surface); border-radius: 14px; padding: 10px 14px; }
.acts { display: flex; gap: 12px; margin-top: 26px; justify-content: center; flex-wrap: wrap; }
.note { color: var(--cv-muted); font-size: 13.5px; margin-top: 18px; }
.oncall { width: 100%; max-width: 1040px; display: grid; gap: 14px; }
.orbline { display: grid; grid-template-columns: auto 1fr; grid-template-rows: auto auto; column-gap: 24px; align-items: center; padding-top: 8px; }
.orbline :deep(.orb) { grid-row: span 2; }
.statusline { font-family: var(--font-display); font-size: 26px; font-weight: 650; letter-spacing: -0.02em; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.statusline .live-dot { background: var(--cv-orchid); }
.statusline .t { font-family: var(--font-sans); font-size: 14px; font-weight: 650; color: var(--cv-muted); letter-spacing: 0; }
.steptrack { display: grid; gap: 6px; max-width: 420px; font-size: 13px; color: var(--cv-muted); font-weight: 600; }
.wave { position: relative; height: 72px; }
.hushnote { position: absolute; left: 50%; top: -6px; transform: translateX(-50%); animation: rise-in 400ms var(--ease-voice) both; }
.info { margin: 0; display: flex; gap: 6px; align-items: center; font-size: 14px; color: var(--cv-muted); }
.captions { display: flex; flex-direction: column; gap: 12px; min-height: 230px; justify-content: flex-end; }
.cap { max-width: 72%; }
.cap.caller { align-self: flex-end; text-align: right; }
.cap .who { display: inline-flex; gap: 7px; align-items: center; font-size: 13px; font-weight: 700; color: var(--cv-muted); margin-bottom: 4px; }
.cap .who i { width: 9px; height: 9px; border-radius: 50%; background: var(--cv-orchid); }
.cap.caller .who i { background: var(--cv-caller); }
.cap p { margin: 0; font-family: var(--font-display); letter-spacing: -0.02em; }
.cap.past p { font-size: calc(19px * var(--cv-caption-scale)); font-weight: 500; color: var(--cv-faint); }
.cap.past .who { display: none; }
.cap.now p { font-size: calc(36px * var(--cv-caption-scale)); font-weight: 700; line-height: 1.15; }
.cap.caller.now p { color: var(--cv-caller); }
.slip { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.slip .label { font-size: 13px; font-weight: 750; color: var(--cv-muted); display: inline-flex; gap: 6px; align-items: center; margin-right: 4px; }
.slip .heard { animation: rise-in 260ms var(--ease-lift) both; }
.slip .ic { color: var(--cv-orchid-ink); display: inline-flex; }
.slip .k { color: var(--cv-muted); font-weight: 550; margin-right: 6px; }
.end { background: var(--cv-surface); border-radius: 28px; padding: 20px 22px; display: grid; gap: 12px; }
.end h2 { font-size: 30px; font-weight: 750; letter-spacing: -0.03em; }
.end h2 span { color: var(--cv-orchid-ink); }
.routepill { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 8px 18px 8px 8px; border-radius: 28px; background: var(--cv-sunk); animation: route-in var(--m-route) var(--ease-voice) both; justify-self: start; }
.routepill ol { display: flex; gap: 16px; margin: 0; padding: 0; list-style: none; font-size: 13.5px; font-weight: 550; flex-wrap: wrap; }
.routepill li { display: flex; gap: 6px; align-items: center; animation: rise-in 300ms var(--ease-voice) both; }
.routepill li b { color: var(--cv-orchid-ink); font-weight: 800; }
.next ul { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 4px; }
.next li { display: flex; gap: 6px; align-items: center; }
.end .acts { justify-content: flex-start; margin-top: 4px; }
.controls { display: grid; gap: 10px; justify-items: center; }
.typed { display: flex; align-items: center; gap: 10px; width: 100%; max-width: 720px; padding: 6px 6px 6px 18px; border-radius: 999px; background: var(--cv-surface); box-shadow: var(--cv-shadow-lift); color: var(--cv-muted); }
.typed input { flex: 1; border: 0; background: transparent; font: inherit; font-size: 16px; color: var(--cv-ink); min-width: 0; height: 40px; }
.typed input:focus { outline: none; }
.btns { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
@media (max-width: 720px) {
  .top { padding: 0 16px; }
  .top .seg { display: none; }
  .top .iconbtn { margin-left: auto; }
  h1 { font-size: 36px; }
  .try { font-size: 20px; }
  .stage { padding: 0 16px 32px; }
  .orbline { grid-template-columns: 1fr; justify-items: center; text-align: center; row-gap: 12px; }
  .orbline :deep(.orb) { grid-row: auto; }
  .statusline { font-size: 21px; justify-content: center; }
  .cap { max-width: 92%; }
  .cap.now p { font-size: 26px; }
}
</style>
