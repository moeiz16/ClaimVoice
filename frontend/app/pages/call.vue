<script setup lang="ts">
// The demo line (DESIGN.md §3): a live call in this browser, in the same shape as the live call. The phone card on
// the left (the pebble swells while idle, follows the microphone while you talk and pulses while ClaimVoice speaks;
// the status, the clock, round buttons for typing, muting and hanging up), the conversation as speech bubbles on the
// right (your words settle from faint to ink), and beneath them the answer sheet filling as the claim is heard, with
// where it goes when the call ends. ?type opens the typed call; ?lang=fr calls in French.
import type { CallMode, ClaimFile, ClaimFileSection, Lang, SectionKey, Slot } from '~/types/api'
import { fmtClock } from '~/utils/format'
import { buildNotice } from '~/utils/notice'
import type { Who } from '~/utils/waveform'

definePageMeta({ layout: 'public' })
const route = useRoute()
const prefs = usePrefs()
const call = useDemoCall()
const { state, lines, interim, stage, slip, notice, hushed, ended, muted, micLevel } = call
const lang = ref<Lang>(route.query.lang === 'fr' ? 'fr' : (prefs.lang.value === 'fr' ? 'fr' : 'en'))
const fr = computed(() => lang.value === 'fr')
const typedText = ref('')
const typedInput = ref<{ inputRef?: HTMLInputElement | null } | null>(null)
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { timer = setInterval(() => { elapsed.value = call.startedAt.value ? Math.floor((Date.now() - call.startedAt.value) / 1000) : 0 }, 500) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
useHead(() => ({ title: fr.value ? 'Appeler la ligne de démo · ClaimVoice' : 'Call the demo line · ClaimVoice', htmlAttrs: { lang: lang.value } }))

const T = computed(() => fr.value
  ? { title: 'Appelez la ligne de démo', lede: 'Imaginez qu\'il vient d\'arriver quelque chose à votre auto ou à votre maison.', note: 'Utilise votre micro dans ce navigateur seulement. Rien de ce que vous dites n\'est gardé après la fermeture de la page.', ring: 'Appeler la ligne de démo', type: 'Écrire plutôt', other: 'Call in English', tryLine: 'Essayez : « Quelqu\'un a reculé dans mon auto au stationnement. »', ringing: 'Ça sonne…', listening: 'À vous. Je vous écoute.', typeTurn: 'À vous. Écrivez votre réponse.', speaking: 'ClaimVoice parle', you: 'Vous', hang: 'Raccrocher', mute: 'Couper la voix', unmute: 'Activer la voix', toTyped: 'Écrire plutôt', placeholder: 'Écrivez ce que vous diriez…', send: 'Envoyer', blocked: 'Votre navigateur n\'a pas permis d\'utiliser le micro. Vous pouvez écrire plutôt.', noRec: 'Ce navigateur ne reconnaît pas la parole, alors l\'appel se fait par écrit. ClaimVoice vous répond quand même à voix haute.', busy: 'Toutes les lignes de démo sont occupées. Réessayez dans une minute.', lost: 'L\'appel a été coupé.', again: 'Rappeler', slip: 'Votre dossier', endH: 'Votre réclamation est faite.', endNone: 'L\'appel est terminé avant la confirmation de la réclamation.', next: 'Et ensuite', back: 'Retour à la page', signin: 'Superviseurs, connexion', left: 'restantes', fills: 'Votre dossier se remplit pendant que vous parlez.', paused: 'Enregistrement en pause', captions: 'Sous-titres', call: 'L\'appel' }
  : { title: 'Call the demo line', lede: 'Pretend something has just happened to your car or your home.', note: 'Uses your microphone in this browser only. Nothing you say is kept after you close the page.', ring: 'Call the demo line', type: 'Type instead', other: 'Appeler en français', tryLine: 'Try: “Someone backed into my car in the Chinook Centre parking lot.”', ringing: 'Ringing…', listening: 'Your turn. I\'m listening.', typeTurn: 'Your turn. Type your answer.', speaking: 'ClaimVoice is speaking', you: 'You', hang: 'Hang up', mute: 'Mute the voice', unmute: 'Turn the voice on', toTyped: 'Type instead', placeholder: 'Type what you would say…', send: 'Send', blocked: 'Your browser didn\'t let us use the microphone. You can type instead.', noRec: 'This browser can\'t recognise speech, so the call is typed. ClaimVoice still answers out loud.', busy: 'All the demo lines are busy. Try again in a minute.', lost: 'The call dropped.', again: 'Call again', slip: 'Your claim file', endH: 'Your claim is in.', endNone: 'The call ended before the claim was confirmed.', next: 'What happens next', back: 'Back to the page', signin: 'Supervisors, sign in', left: 'left', fills: 'Your claim file fills in as you talk.', paused: 'Recording paused · card number', captions: 'Captions', call: 'The call' })

function ring(mode: CallMode, l: Lang = lang.value) {
  lang.value = l
  void call.start({ mode, lang: l })
}
onMounted(() => { if ('type' in route.query) ring('typed') })
watch(() => call.mode.value, async (m) => { if (m === 'typed') { await nextTick(); typedInput.value?.inputRef?.focus() } })

const intro = computed(() => ['idle', 'blocked', 'busy', 'lost'].includes(state.value))
const live = computed(() => ['ringing', 'listening', 'speaking'].includes(state.value))
const orbState = computed(() => (state.value === 'speaking' ? 'speaking' : state.value === 'listening' ? 'listening' : state.value === 'ringing' || state.value === 'starting' ? 'ringing' : state.value === 'ended' ? 'ended' : 'idle'))
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
const langItems = computed(() => [{ label: 'English', value: 'en', disabled: live.value }, { label: 'Français', value: 'fr', disabled: live.value }])

// The conversation: the last few lines as bubbles (interim words while you're still talking).
const recent = computed(() => lines.value.slice(-6))

// The loss notice from what the call has heard so far. The demo line sends slots one at a time, so each is placed
// in its section by its key; the next steps are left to section 8, where they're read in full at the end.
const SECTION_OF: [RegExp, SectionKey][] = [
  [/^(consent|caller_|callback_|preferred_language)/, 'caller'],
  [/^(policy|identity|insured)/, 'policy'],
  [/^(injury|danger|emergency|power_out|hurt|safety)/, 'safety'],
  [/^(loss_|what$|when$|where$)/, 'loss'],
  [/^photo/, 'photos'],
  [/^(coverage|deductible|covered)/, 'coverage'],
]
const ORDER: SectionKey[] = ['caller', 'policy', 'safety', 'loss', 'details', 'photos', 'coverage']
const SECTION_LABEL: Record<Lang, Partial<Record<SectionKey, string>>> = {
  en: { caller: 'Caller', policy: 'Policy', safety: 'Safety', loss: 'What happened', details: 'Damage', photos: 'Photos', coverage: 'Coverage' },
  fr: { caller: 'Appelant', policy: 'Police', safety: 'Sécurité', loss: 'Ce qui s\'est passé', details: 'Dommages', photos: 'Photos', coverage: 'Couverture' },
}
const NEXT_KEYS = new Set(['next_steps_given', 'adjuster_contact_window'])
const sectionOf = (key: string): SectionKey => SECTION_OF.find(([re]) => re.test(key))?.[1] ?? 'details'
const file = computed<ClaimFile | null>(() => {
  const by = new Map<SectionKey, Slot[]>()
  for (const s of slip.value) {
    if (NEXT_KEYS.has(s.key)) continue
    const k = sectionOf(s.key)
    by.set(k, [...(by.get(k) ?? []), s])
  }
  const sections: ClaimFileSection[] = ORDER.filter(k => by.has(k)).map(k => ({ key: k, label: SECTION_LABEL[lang.value][k] ?? k, slots: by.get(k)! }))
  return { callId: 'demo-line', claimId: null, lossType: null, lossTypeLabel: null, progress: 0, missing: [], sections }
})
const sections = computed(() => buildNotice(file.value, stage.value?.step ?? 1, !!ended.value))
function sendTyped() { call.sendTyped(typedText.value); typedText.value = '' }
</script>

<template>
  <div class="callpage" :class="state">
    <header class="top">
      <CvLogo />
      <div class="right">
        <UTabs v-model="lang" :items="langItems" :content="false" size="sm" color="neutral" class="hide-phone" aria-label="Language / Langue">
          <template #default="{ item }">
            <span :lang="item.value === 'fr' ? 'fr' : 'en'">{{ item.label }}</span>
          </template>
        </UTabs>
        <UButton to="/sign-in" color="neutral" variant="ghost" icon="i-lucide-log-in" :lang="lang" :aria-label="T.signin" class="whitespace-nowrap">
          <span class="hide-phone">{{ T.signin }}</span>
        </UButton>
        <UButton to="/#ring" color="neutral" variant="soft" icon="i-lucide-x" :aria-label="T.back" class="rounded-full" />
      </div>
    </header>

    <main class="wrap">
      <h1>{{ T.title }}</h1>
      <p class="note">
        <UIcon name="i-lucide-mic" class="size-4 shrink-0" />{{ T.note }}
      </p>

      <div class="room">
        <section class="phone" :aria-label="T.call">
          <DemoOrb :state="orbState" :level="micLevel" :size="132" :typed="call.mode.value === 'typed'" />
          <p v-if="!intro" class="status" role="status">
            <span v-if="live" class="live-dot" aria-hidden="true" />{{ status || (state === 'ended' ? T.endH : '') }}
          </p>
          <p v-if="live && call.startedAt.value" class="clock num">
            {{ fmtClock(elapsed) }} · {{ fmtClock(remaining) }} {{ T.left }}
          </p>
          <div v-if="live" class="lvl">
            <LiveWave seed-key="demo-line" :source="levelSource" :label="T.call" />
          </div>
          <div v-if="intro" class="btns">
            <RoundButton v-if="state !== 'blocked'" icon="i-lucide-phone" :label="T.ring" tone="jade" size="lg" class="answer" @click="ring('browser_speech')" />
            <RoundButton icon="i-lucide-keyboard" :label="T.type" size="lg" :tone="state === 'blocked' ? 'jade' : 'neutral'" @click="ring('typed')" />
            <RoundButton icon="i-lucide-languages" :label="T.other" size="lg" :lang="fr ? 'en' : 'fr'" @click="ring('browser_speech', fr ? 'en' : 'fr')" />
          </div>
          <div v-else-if="state !== 'ended'" class="btns">
            <RoundButton v-if="call.mode.value !== 'typed'" icon="i-lucide-keyboard" :label="T.toTyped" size="lg" @click="call.switchToTyped()" />
            <RoundButton :icon="muted ? 'i-lucide-volume-x' : 'i-lucide-volume-2'" :label="muted ? T.unmute : T.mute" :pressed="muted" size="lg" @click="muted = !muted" />
            <RoundButton icon="i-lucide-phone-off" :label="T.hang" tone="urgent" size="lg" @click="call.hangUp()" />
          </div>
          <CvTag v-if="hushed" kind="jade" icon="lock" class="hushnote">
            {{ notice ?? T.paused }}
          </CvTag>
        </section>

        <section class="talk" :aria-label="T.captions">
          <ol v-if="intro" class="bubbles" aria-live="polite">
            <li class="b cv">
              <small>ClaimVoice</small><p>{{ T.lede }}</p>
            </li>
            <li class="b caller">
              <small>{{ T.you }}</small><p>{{ T.tryLine }}</p>
            </li>
          </ol>
          <ol v-else class="bubbles" aria-live="polite">
            <li v-for="l in recent" :key="l.id" class="b" :class="l.who" :lang="lang">
              <small>{{ l.who === 'cv' ? 'ClaimVoice' : T.you }}</small>
              <p v-if="l.who === 'cv'">
                {{ l.text }}
              </p>
              <p v-else>
                <TranscriptText :text="l.text" :turn-id="l.id" />
              </p>
            </li>
            <li v-if="interim && state !== 'ended'" class="b caller" aria-hidden="true">
              <small>{{ T.you }}</small>
              <p><span v-for="(w, i) in interim.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ `${w} ` }}</span></p>
            </li>
          </ol>
          <form v-if="!intro && state !== 'ended' && call.mode.value === 'typed'" class="typed" @submit.prevent="sendTyped">
            <UInput
              id="typed" ref="typedInput" v-model="typedText" :placeholder="T.placeholder" :aria-label="T.placeholder" autocomplete="off" maxlength="400"
              size="xl" icon="i-lucide-keyboard" class="flex-1"
            />
            <UButton type="submit" size="xl" icon="i-lucide-send" :disabled="!typedText.trim()">
              {{ T.send }}
            </UButton>
          </form>
          <div v-if="state === 'blocked' || state === 'busy' || state === 'lost' || (call.noRecognition.value && call.mode.value === 'typed' && !intro)" class="notes">
            <StateNote v-if="state === 'blocked'" kind="error" :title="T.blocked" />
            <StateNote v-if="state === 'busy'" kind="info" :title="T.busy" />
            <StateNote v-if="state === 'lost'" kind="error" :title="T.lost" :body="call.error.value" />
            <UAlert v-if="call.noRecognition.value && call.mode.value === 'typed' && !intro" color="neutral" variant="subtle" icon="i-lucide-keyboard" :title="T.noRec" />
          </div>
        </section>
      </div>

      <AnswerSheet
        v-if="!intro" class="answers" :title="T.slip" :sections="sections" :step="stage?.step ?? 1" :ended="!!ended" :language="lang" :words="lang"
        :reference="ended?.claimNumber ?? null"
      >
        <template v-if="!sections.length && !ended" #before>
          <p class="fills" :lang="lang">
            {{ T.fills }}
          </p>
        </template>
        <template #after>
          <EndRoute
            v-if="ended" :route="ended.claimNumber ? ended.route : null" :next-steps="ended.nextSteps" :lang="lang"
            :title="ended.claimNumber ? T.endH : T.endNone" :reference="ended.claimNumber" :next-title="T.next"
          >
            <template #actions>
              <UButton icon="i-lucide-phone" @click="ring(call.mode.value)">
                {{ T.again }}
              </UButton>
              <UButton to="/" color="neutral" variant="soft">
                {{ T.back }}
              </UButton>
            </template>
          </EndRoute>
        </template>
      </AnswerSheet>
    </main>
  </div>
</template>

<style scoped>
.callpage { min-height: 100dvh; background: var(--cv-bg); }
.top { display: flex; align-items: center; gap: 14px; padding: 18px 40px; width: min(1280px, 100%); margin: 0 auto; }
.top .right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.wrap { width: min(1280px, 100%); margin: 0 auto; padding: 12px 40px 64px; }
h1 { font-size: 60px; font-weight: 900; letter-spacing: -0.03em; line-height: 1; }
.note { margin: 12px 0 0; display: flex; gap: 8px; align-items: flex-start; color: var(--cv-muted); font-size: 15px; max-width: 62ch; }
.note .size-4 { margin-top: 3px; }
.room { margin-top: 28px; display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 28px; align-items: start; }
.phone { display: grid; justify-items: center; gap: 12px; padding: 36px 20px 26px; border-radius: 36px; background: linear-gradient(180deg, var(--cv-jade-wash), var(--cv-surface) 62%); box-shadow: var(--cv-shadow-soft); text-align: center; }
.status { margin: 14px 0 0; display: inline-flex; gap: 8px; align-items: center; font-weight: 600; font-size: 15px; }
.clock { margin: 0; color: var(--cv-muted); font-size: 13.5px; }
.lvl { width: 100%; height: 40px; }
.btns { margin-top: 10px; display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.answer :deep(.c) { width: 72px; height: 72px; font-size: 28px; }
.hushnote { animation: rise 400ms var(--ease-tide) both; }
.talk { min-width: 0; display: grid; gap: 14px; }
.bubbles { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; min-height: 280px; justify-content: flex-end; }
.b { max-width: 82%; padding: 12px 18px 14px; border-radius: 24px 24px 24px 6px; background: var(--cv-surface); align-self: flex-start; animation: inflate-l var(--m-inflate) var(--ease-tide) both; transform-origin: 0 100%; box-shadow: var(--cv-shadow-soft); }
.b.caller { align-self: flex-end; border-radius: 24px 24px 6px 24px; background: var(--cv-sand); transform-origin: 100% 100%; }
.b small { display: block; font-size: 12.5px; font-weight: 600; color: var(--cv-jade-ink); margin-bottom: 2px; }
.b.caller small { color: var(--cv-caller); text-align: right; }
.b p { margin: 0; font-size: calc(18px * var(--cv-caption-scale)); line-height: 1.45; }
.b:last-child p { font-family: var(--font-round); font-weight: 800; font-size: calc(22px * var(--cv-caption-scale)); line-height: 1.3; }
.typed { display: flex; gap: 8px; align-items: center; padding: 8px; border-radius: 24px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.typed :deep(input) { box-shadow: none; }
.notes { display: grid; gap: 8px; }
.answers { margin-top: 44px; }
.fills { margin: 0; color: var(--cv-muted); font-size: 14px; }
@media (max-width: 1000px) {
  .room { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .top { padding: 12px 16px; }
  .top .hide-phone { display: none; }
  .wrap { padding: 8px 16px 48px; }
  h1 { font-size: 38px; }
  .phone { padding: 24px 12px 18px; border-radius: 28px; }
  .bubbles { min-height: 0; }
  .b { max-width: 94%; }
  .typed { flex-wrap: wrap; }
  .typed :deep(.flex-1) { flex-basis: 100%; }
}
</style>
