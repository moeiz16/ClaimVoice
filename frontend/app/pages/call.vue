<script setup lang="ts">
// Ring the demo line (DESIGN.md §4): a live call in this browser, on the desk's grammar. A quiet top line, the slate
// (the title and the microphone prerequisite), then the tape: the orb is its key (it breathes while idle, follows
// the microphone while you talk and pulses while ClaimVoice speaks), ClaimVoice's line is written above the wave and
// yours below it (your words settle from faint to ink), the typed call and the call's buttons sit at its foot.
// Beneath, the loss notice fills in as the claim is heard, and section 8 unfurls the route when the call ends.
// ?type opens the typed call; ?lang=fr calls in French.
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
useHead(() => ({ title: fr.value ? 'Appeler la ligne de démo · ClaimVoice' : 'Ring the demo line · ClaimVoice', htmlAttrs: { lang: lang.value } }))

const T = computed(() => fr.value
  ? { title: 'Appeler la ligne de démo', lede: 'Imaginez qu\'il vient d\'arriver quelque chose à votre auto ou à votre maison.', note: 'Utilise votre micro dans ce navigateur seulement. Rien de ce que vous dites n\'est gardé après la fermeture de la page.', ring: 'Appeler la ligne de démo', type: 'Écrire plutôt', other: 'Call in English', tryLine: 'Essayez : « Quelqu\'un a reculé dans mon auto au stationnement. »', ringing: 'Ça sonne…', listening: 'À vous. Je vous écoute.', typeTurn: 'À vous. Écrivez votre réponse.', speaking: 'ClaimVoice parle', you: 'Vous', hang: 'Raccrocher', mute: 'Couper la voix', unmute: 'Activer la voix', toTyped: 'Écrire plutôt', placeholder: 'Écrivez ce que vous diriez…', send: 'Envoyer', blocked: 'Votre navigateur n\'a pas permis d\'utiliser le micro. Vous pouvez écrire plutôt.', noRec: 'Ce navigateur ne reconnaît pas la parole, alors l\'appel se fait par écrit. ClaimVoice vous répond quand même à voix haute.', busy: 'Toutes les lignes de démo sont occupées. Réessayez dans une minute.', lost: 'L\'appel a été coupé.', again: 'Rappeler', slip: 'Votre dossier', endH: 'Votre réclamation est faite.', endNone: 'L\'appel est terminé avant la confirmation de la réclamation.', next: 'Et ensuite', back: 'Retour à la page', signin: 'Superviseurs, connexion', left: 'restantes', fills: 'Votre dossier se remplit pendant que vous parlez.', paused: 'Enregistrement en pause', captions: 'Sous-titres', call: 'L\'appel' }
  : { title: 'Ring the demo line', lede: 'Pretend something has just happened to your car or your home.', note: 'Uses your microphone in this browser only. Nothing you say is kept after you close the page.', ring: 'Ring the demo line', type: 'Type instead', other: 'Appeler en français', tryLine: 'Try: “Someone backed into my car in the Chinook Centre parking lot.”', ringing: 'Ringing…', listening: 'Your turn. I\'m listening.', typeTurn: 'Your turn. Type your answer.', speaking: 'ClaimVoice is speaking', you: 'You', hang: 'Hang up', mute: 'Mute the voice', unmute: 'Turn the voice on', toTyped: 'Type instead', placeholder: 'Type what you would say…', send: 'Send', blocked: 'Your browser didn\'t let us use the microphone. You can type instead.', noRec: 'This browser can\'t recognise speech, so the call is typed. ClaimVoice still answers out loud.', busy: 'All the demo lines are busy. Try again in a minute.', lost: 'The call dropped.', again: 'Ring again', slip: 'Your claim file', endH: 'Your claim is in.', endNone: 'The call ended before the claim was confirmed.', next: 'What happens next', back: 'Back to the page', signin: 'Supervisors, sign in', left: 'left', fills: 'Your claim file fills in as you talk.', paused: 'Recording paused · card number', captions: 'Captions', call: 'The call' })

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

// The captions on the tape: ClaimVoice's latest line above, yours below (interim words while you're still talking).
const lastCv = computed(() => [...lines.value].reverse().find(l => l.who === 'cv') ?? null)
const lastYou = computed(() => [...lines.value].reverse().find(l => l.who === 'caller') ?? null)

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
const turns = computed(() => lines.value.map(l => ({ id: l.id, text: l.text })))
function sendTyped() { call.sendTyped(typedText.value); typedText.value = '' }
</script>

<template>
  <div class="callpage" :class="state">
    <header class="top">
      <CvLogo />
      <div class="right">
        <UButton to="/sign-in" color="neutral" variant="link" icon="i-lucide-log-in" :lang="lang" :aria-label="T.signin" class="whitespace-nowrap">
          <span class="hide-phone">{{ T.signin }}</span>
        </UButton>
        <UTabs v-model="lang" :items="langItems" :content="false" variant="pill" size="sm" color="neutral" class="hide-phone" aria-label="Language / Langue">
          <template #default="{ item }">
            <span :lang="item.value === 'fr' ? 'fr' : 'en'">{{ item.label }}</span>
          </template>
        </UTabs>
        <UButton to="/#ring" color="neutral" variant="ghost" icon="i-lucide-x" :aria-label="T.back" />
      </div>
    </header>

    <Slate :title="T.title" :caption="T.note" />

    <Tape :label="T.call">
      <template #key>
        <div class="orbkey">
          <DemoOrb :state="orbState" :level="micLevel" :size="112" :typed="call.mode.value === 'typed'" />
        </div>
        <div v-if="!intro" class="statusline" role="status">
          <span v-if="live" class="live-dot" aria-hidden="true" />{{ status }}
          <span v-if="live && call.startedAt.value" class="t num">{{ fmtClock(elapsed) }} · {{ fmtClock(remaining) }} {{ T.left }}</span>
        </div>
      </template>

      <template #above>
        <div aria-live="polite" class="capwrap" :aria-label="T.captions">
          <Transition name="cap" mode="out-in">
            <div v-if="intro" key="lede" class="cap">
              <p>{{ T.lede }}</p>
            </div>
            <div v-else-if="lastCv" :key="lastCv.id" class="cap">
              <small class="who"><i aria-hidden="true" />ClaimVoice</small>
              <p>{{ lastCv.text }}</p>
            </div>
          </Transition>
        </div>
      </template>

      <LiveWave seed-key="demo-line" :source="levelSource" />

      <template v-if="hushed" #pins>
        <div class="pinrow">
          <CvTag kind="orchid" icon="lock" class="hushnote">
            {{ notice ?? T.paused }}
          </CvTag>
        </div>
      </template>

      <template #below>
        <div aria-live="polite" class="capwrap">
          <Transition name="cap" mode="out-in">
            <div v-if="intro" key="try" class="cap caller">
              <p>{{ T.tryLine }}</p>
            </div>
            <div v-else-if="interim && state !== 'ended'" key="interim" class="cap caller" aria-hidden="true">
              <small class="who"><i />{{ T.you }}</small>
              <p><span v-for="(w, i) in interim.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ `${w} ` }}</span></p>
            </div>
            <div v-else-if="lastYou" :key="lastYou.id" class="cap caller">
              <small class="who"><i aria-hidden="true" />{{ T.you }}</small>
              <p><TranscriptText :text="lastYou.text" :turn-id="lastYou.id" /></p>
            </div>
          </Transition>
        </div>
      </template>

      <template #foot>
        <div v-if="intro" class="callbtns">
          <UButton v-if="state !== 'blocked'" icon="i-lucide-mic" @click="ring('browser_speech')">
            {{ T.ring }}
          </UButton>
          <UButton icon="i-lucide-keyboard" :color="state === 'blocked' ? 'primary' : 'neutral'" :variant="state === 'blocked' ? 'solid' : 'soft'" @click="ring('typed')">
            {{ T.type }}
          </UButton>
          <UButton icon="i-lucide-languages" color="neutral" variant="soft" :lang="fr ? 'en' : 'fr'" @click="ring('browser_speech', fr ? 'en' : 'fr')">
            {{ T.other }}
          </UButton>
        </div>
        <template v-else-if="state !== 'ended'">
          <form v-if="call.mode.value === 'typed'" class="typed" @submit.prevent="sendTyped">
            <UInput
              id="typed" ref="typedInput" v-model="typedText" :placeholder="T.placeholder" :aria-label="T.placeholder" autocomplete="off" maxlength="400"
              size="xl" icon="i-lucide-keyboard" class="flex-1"
            />
            <UButton type="submit" size="xl" icon="i-lucide-send" :disabled="!typedText.trim()">
              {{ T.send }}
            </UButton>
          </form>
          <div class="callbtns">
            <UButton v-if="call.mode.value !== 'typed'" size="md" color="neutral" variant="soft" icon="i-lucide-keyboard" @click="call.switchToTyped()">
              {{ T.toTyped }}
            </UButton>
            <UButton size="md" color="neutral" variant="soft" :icon="muted ? 'i-lucide-volume-x' : 'i-lucide-volume-2'" :aria-pressed="muted" @click="muted = !muted">
              {{ muted ? T.unmute : T.mute }}
            </UButton>
            <UButton size="md" color="error" icon="i-lucide-phone-off" @click="call.hangUp()">
              {{ T.hang }}
            </UButton>
          </div>
        </template>
      </template>
    </Tape>

    <div v-if="state === 'blocked' || state === 'busy' || state === 'lost' || (call.noRecognition.value && call.mode.value === 'typed' && !intro)" class="notes">
      <StateNote v-if="state === 'blocked'" kind="error" :title="T.blocked" />
      <StateNote v-if="state === 'busy'" kind="info" :title="T.busy" />
      <StateNote v-if="state === 'lost'" kind="error" :title="T.lost" :body="call.error.value" />
      <UAlert v-if="call.noRecognition.value && call.mode.value === 'typed' && !intro" color="neutral" variant="subtle" icon="i-lucide-keyboard" :title="T.noRec" />
    </div>

    <LossNotice
      v-if="!intro" :title="T.slip" :sections="sections" :step="stage?.step ?? 1" :ended="!!ended" :turns="turns" :language="lang" :words="lang"
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
    </LossNotice>
  </div>
</template>

<style scoped>
.callpage { min-height: 100dvh; background: var(--cv-bg); padding-bottom: 32px; }
.top { display: flex; align-items: center; gap: 14px; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.top .right { margin-left: auto; display: flex; align-items: center; gap: 10px; }

/* The orb is the tape's key; its status and the call's clock sit under it. */
.orbkey { display: grid; place-items: center; padding: 18px 0; }
.statusline { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: center; text-align: center; font-size: 14px; font-weight: 650; }
.statusline .live-dot { background: var(--cv-orchid); }
.statusline .t { flex-basis: 100%; font-size: 13px; color: var(--cv-muted); }

.capwrap { min-height: 1.22em; }
.cap p { margin: 0; }
.cap .who {
  display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
  font-family: var(--font-sans); font-variation-settings: normal; font-size: 12.5px; font-weight: 650; letter-spacing: 0; color: var(--cv-muted); line-height: 1.3;
}
.cap .who i { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); }
.cap.caller .who { justify-content: flex-end; }
.cap.caller .who i { background: var(--cv-caller); }
.cap-enter-active, .cap-leave-active { transition: opacity 180ms var(--ease-voice); }
.cap-enter-from, .cap-leave-to { opacity: 0; }
.pinrow { display: flex; justify-content: center; }
.hushnote { animation: rise-in 400ms var(--ease-voice) both; }

.callbtns { display: flex; gap: 8px; flex-wrap: wrap; }
.typed { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }

.notes { display: grid; gap: 8px; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.fills { margin: 0; color: var(--cv-muted); font-size: 14px; }

@media (max-width: 1100px) {
  .orbkey { padding: 4px 18px 4px 4px; }
  .statusline { justify-content: flex-start; text-align: left; align-self: center; }
  .statusline .t { flex-basis: auto; }
}
@media (max-width: 720px) {
  .top { padding: 10px 16px; }
  .top .hide-phone { display: none; }
  .notes { padding: 12px 16px; }
  .typed { flex-wrap: wrap; }
  .typed :deep(.flex-1) { flex-basis: 100%; }
  .callbtns :deep(button) { flex: 1 1 auto; }
}
</style>
