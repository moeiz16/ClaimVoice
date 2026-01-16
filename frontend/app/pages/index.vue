<script setup lang="ts">
// The landing page (DESIGN.md §6): an incoming claim call you answer. The headline, then the call as a phone shows
// it beside the conversation: pressing Answer plays the call, its bubbles inflating as each line is said, and the
// claim filling as pebbles underneath (the card number hushed, the route turning in at the end). Then the demo line,
// what each person gets, the safeguards and the compliance line. Nothing auto-plays.
// Query flags for review: ?t=<s>|end, ?play, ?read (and ?still, ?theme, applied app-wide).
import { builtInCall, noticeItems, parseLandingCall, slipAt, type LandingCall } from '~/utils/landingCall'
import { fmtDurationWords } from '~/utils/format'
import { stripCardToken, turnAt } from '~/utils/transcript'

definePageMeta({ layout: 'public' })

const prefs = usePrefs()
const lang = computed<'en' | 'fr'>(() => (prefs.lang.value === 'fr' ? 'fr' : 'en'))
const route = useRoute()

const COPY = {
  en: {
    nav: ['Hear a call', 'What your team gets', 'Safeguards'],
    navLabel: 'Sections',
    signin: 'Sign in',
    eyebrow: 'For claims teams at insurers and agencies · English and French · every hour of the day',
    h1: 'The claims line that always picks up.',
    lede: 'ClaimVoice answers your claims line at any hour, in English or French. It takes the first report kindly, asks the right follow-up questions, and hands your team a claim file where every answer links back to the words it came from.',
    stage: {
      incoming: 'Incoming claim call', when: 'Thursday 8 January, 2:14 a.m.', who: 'Dana Whitcombe', about: 'Policyholder · Calgary, in a Chinook windstorm',
      answer: 'Answer', pause: 'Pause', resume: 'Resume', again: 'Hear it again', read: 'Read instead', captions: 'Captions',
      onCall: 'On the call', paused: 'Paused', ended: 'Call ended · claim filed', cv: 'ClaimVoice', caller: 'Dana',
      filed: 'Filed while Dana talks', filedEmpty: 'Each answer lands here as it is heard, with the moment it was said.',
      fromPolicy: 'from the policy', notTaken: 'Card number not taken', removed: 'removed', where: 'Where it goes:',
      sample: 'Sample call, shortened. The voices are synthetic.', readLabel: 'The whole call, as text',
    },
    readBack: 'Read back, and Dana agreed',
    ringH: 'Call the demo line yourself.',
    ringP: 'Pretend something has just happened to your car or your home. ClaimVoice will take the claim, live, in this browser.',
    ringTry: 'Try: “Someone backed into my car in the Chinook Centre parking lot.”',
    ringBtns: ['Call the demo line', 'Type instead', 'Appeler en français'],
    ringNote: 'Uses your microphone in this browser only. Nothing you say is kept after you close the page.',
    saidH: 'What your team gets, by role.',
    rows: [
      { role: 'Policyholder', ask: 'What does the caller get?', line: '“Is everyone safe right now? Then let\'s get your claim started. It takes about four minutes.”', caller: false, pills: ['A claim number before hanging up', 'A photo link by text', 'A time someone will call'], tag: null as null | { kind: 'urgent' | 'fast', icon: string, text: string } },
      { role: 'Intake team', ask: 'What does the intake team get?', line: '“The wind tore the cover off my gas meter and I can smell gas.”', caller: true, pills: ['The caller told to leave and call 911', 'A summary, so nobody asks twice'], tag: { kind: 'urgent' as const, icon: 'i-lucide-triangle-alert', text: 'Urgent safety, waiting for a person' } },
      { role: 'Adjuster', ask: 'What does the adjuster get?', line: '“Here\'s what I have. Is that right?”', caller: false, pills: ['Every answer linked to the words it came from', 'The recording, by speaker'], tag: { kind: 'fast' as const, icon: 'i-lucide-check', text: 'A route, with reasons in plain words' } },
    ],
    guardsH: 'Three promises, kept on every call.',
    guards: [
      { icon: 'i-lucide-shield-check', h: 'Recording consent comes first', p: 'Every call opens by asking. Where both people must agree to be recorded, nothing is kept until the caller says yes.', demo: '“This call is recorded so we get your claim right. Is that okay?”', hush: false, caller: false },
      { icon: 'i-lucide-credit-card', h: 'Card numbers are never taken', p: 'If a caller starts reading a card number, ClaimVoice stops them, and that moment is cut from the recording and the transcript.', demo: '“It\'s four-five', hush: true, caller: true },
      { icon: 'i-lucide-user-round', h: 'A person can take over any call', p: 'Callers can ask for a person at any time. Supervisors can listen, pass ClaimVoice a note, or take the call. Nothing is ever denied automatically.', demo: '“Of course. I\'m bringing in Renée now.”', hush: false, caller: false },
    ],
    removed: 'removed',
    comply: 'Designed to support the NAIC model bulletin on insurers\' use of AI, state call-recording consent rules, PCI DSS, GLBA, PIPEDA and Québec\'s Law 25. In English and French.',
    foot: 'Built for claims teams at regional insurers and agencies.',
    footLinks: ['Sign in', 'Français', 'Privacy'],
  },
  fr: {
    nav: ['Écouter un appel', 'Ce que votre équipe reçoit', 'Garanties'],
    navLabel: 'Sections',
    signin: 'Connexion',
    eyebrow: 'Pour les équipes de réclamations des assureurs et cabinets · en français et en anglais · à toute heure',
    h1: 'La ligne de réclamations qui répond toujours.',
    lede: 'ClaimVoice répond à votre ligne de réclamations à toute heure, en français ou en anglais. Il prend la première déclaration avec douceur, pose les bonnes questions et remet à votre équipe un dossier où chaque réponse renvoie aux mots d\'où elle vient.',
    stage: {
      incoming: 'Appel de réclamation entrant', when: 'Jeudi 8 janvier, 2 h 14', who: 'Dana Whitcombe', about: 'Assurée · Calgary, pendant une tempête chinook',
      answer: 'Répondre', pause: 'Pause', resume: 'Reprendre', again: 'Réécouter', read: 'Lire plutôt', captions: 'Sous-titres',
      onCall: 'En ligne', paused: 'En pause', ended: 'Appel terminé · dossier ouvert', cv: 'ClaimVoice', caller: 'Dana',
      filed: 'Noté pendant que Dana parle', filedEmpty: 'Chaque réponse arrive ici quand elle est entendue, avec le moment où elle a été dite.',
      fromPolicy: 'selon la police', notTaken: 'Numéro de carte non pris', removed: 'retiré', where: 'Acheminement :',
      sample: 'Appel d\'exemple, abrégé. Les voix sont synthétiques.', readLabel: 'Tout l\'appel, en texte',
    },
    readBack: 'Relu, et Dana est d\'accord',
    ringH: 'Appelez la ligne de démo vous-même.',
    ringP: 'Imaginez qu\'il vient d\'arriver quelque chose à votre auto ou à votre maison. ClaimVoice prendra la réclamation, en direct, dans ce navigateur.',
    ringTry: 'Essayez : « Quelqu\'un a reculé dans mon auto au stationnement du Carrefour Laval. »',
    ringBtns: ['Appeler la ligne de démo', 'Écrire plutôt', 'Call in English'],
    ringNote: 'Utilise votre micro dans ce navigateur seulement. Rien de ce que vous dites n\'est gardé après la fermeture de la page.',
    saidH: 'Ce que votre équipe reçoit, selon le rôle.',
    rows: [
      { role: 'Assuré', ask: 'Que reçoit l\'appelant ?', line: '« Est-ce que tout le monde est en sécurité? Alors, commençons votre réclamation. Ça prend environ quatre minutes. »', caller: false, pills: ['Un numéro de réclamation avant de raccrocher', 'Un lien pour photos par texto', 'L\'heure où on les rappellera'], tag: null as null | { kind: 'urgent' | 'fast', icon: string, text: string } },
      { role: 'Équipe d\'accueil', ask: 'Que reçoit l\'équipe d\'accueil ?', line: '« Le vent a arraché le couvercle de mon compteur de gaz et ça sent le gaz. »', caller: true, pills: ['L\'appelant invité à sortir et à faire le 911', 'Un résumé, pour ne rien redemander'], tag: { kind: 'urgent' as const, icon: 'i-lucide-triangle-alert', text: 'Sécurité urgente, attend une personne' } },
      { role: 'Expert en sinistres', ask: 'Que reçoit l\'expert ?', line: '« Voici ce que j\'ai. C\'est bien ça? »', caller: false, pills: ['Chaque réponse reliée aux mots d\'où elle vient', 'L\'enregistrement, par voix'], tag: { kind: 'fast' as const, icon: 'i-lucide-check', text: 'Un acheminement, avec des raisons claires' } },
    ],
    guardsH: 'Trois promesses, tenues à chaque appel.',
    guards: [
      { icon: 'i-lucide-shield-check', h: 'Le consentement d\'abord', p: 'Chaque appel commence par la question. Là où les deux personnes doivent accepter, rien n\'est gardé avant le oui de l\'appelant.', demo: '« L\'appel est enregistré pour bien traiter votre réclamation. Ça vous convient? »', hush: false, caller: false },
      { icon: 'i-lucide-credit-card', h: 'Jamais de numéro de carte', p: 'Si un appelant commence à lire un numéro de carte, ClaimVoice l\'arrête, et ce moment est retiré de l\'enregistrement et de la transcription.', demo: '« C\'est quatre-cinq', hush: true, caller: true },
      { icon: 'i-lucide-user-round', h: 'Une personne peut prendre l\'appel', p: 'L\'appelant peut demander une personne en tout temps. Les superviseurs peuvent écouter, glisser une note à ClaimVoice ou prendre l\'appel. Rien n\'est jamais refusé automatiquement.', demo: '« Bien sûr. Je fais venir Renée. »', hush: false, caller: false },
    ],
    removed: 'retiré',
    comply: 'Conçu pour soutenir le bulletin type de la NAIC sur l\'usage de l\'IA par les assureurs, les règles de consentement à l\'enregistrement, PCI DSS, GLBA, la LPRPDE et la Loi 25 du Québec. En français et en anglais.',
    foot: 'Conçu pour les équipes de réclamations des assureurs et cabinets régionaux.',
    footLinks: ['Connexion', 'English', 'Confidentialité'],
  },
}
const c = computed(() => COPY[lang.value])
useHead(() => ({ title: lang.value === 'fr' ? 'ClaimVoice · la ligne de réclamations qui répond toujours' : 'ClaimVoice · the claims line that always picks up', htmlAttrs: { lang: lang.value } }))

// ------------------------------------------------------------- language and view switches (Nuxt UI tabs)
const langItems = [{ label: 'English', short: 'EN', value: 'en' }, { label: 'Français', short: 'FR', value: 'fr' }]
const langModel = computed<string>({
  get: () => lang.value,
  set: (v) => { prefs.lang.value = v === 'fr' ? 'fr' : 'en' },
})
const reading = ref(false)

// ------------------------------------------------------------- the call
const call = ref<LandingCall>(builtInCall(lang.value))
const audioBase = computed(() => (lang.value === 'fr' ? '/audio/dana-call-fr' : '/audio/dana-call'))
const sources = ref<{ src: string, type: string }[]>([])
async function loadCall() {
  call.value = builtInCall(lang.value)
  sources.value = []
  try {
    const res = await fetch(`${audioBase.value}.json`)
    const ct = res.headers.get('content-type') ?? ''
    if (!res.ok || !ct.includes('json')) return
    const parsed = parseLandingCall(await res.json())
    if (parsed) {
      call.value = parsed
      sources.value = [{ src: `${audioBase.value}.m4a`, type: 'audio/mp4' }, { src: `${audioBase.value}.ogg`, type: 'audio/ogg; codecs=opus' }]
    }
  }
  catch { /* keep the built-in script */ }
}
const duration = computed(() => call.value.durationSeconds)
const player = useCallPlayer(duration, sources)
const { t, playing } = player
watch(lang, () => { player.pause(); player.seek(0); void loadCall() })

const idx = computed(() => turnAt(call.value.turns, t.value))
const allItems = computed(() => noticeItems(call.value, c.value.readBack))
const filled = computed(() => slipAt(allItems.value, t.value))
const showRoute = computed(() => t.value >= duration.value - 0.05)
const durationWords = computed(() => fmtDurationWords(duration.value, lang.value))
const stageCopy = computed(() => ({ ...c.value.stage, sample: `${c.value.stage.sample} ${durationWords.value}.` }))
const finished = computed(() => call.value.turns.filter(x => x.to <= t.value))
const lastFinal = computed(() => {
  const f = finished.value[finished.value.length - 1]
  return f ? { ...f, text: stripCardToken(f.text) } : null
})

function seekTurn(dir: 1 | -1) {
  const i = idx.value + dir
  const turn = call.value.turns[Math.max(0, Math.min(call.value.turns.length - 1, i))]
  if (turn) player.seek(turn.from + 0.01)
}
function seekMoment(dir: 1 | -1) {
  const ms = call.value.moments
  const next = dir > 0 ? ms.find(m => m.at > t.value + 0.2) : [...ms].reverse().find(m => m.at < t.value - 0.2)
  if (next) player.seek(next.at)
}
function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable)) return
  // Tabs move between their options with the arrow keys; leave those alone.
  if (el?.closest('[role="tablist"]')) return
  // On a button or link, Space and Enter keep their own meaning; the call shortcuts still work after pressing Play.
  if (el && ['BUTTON', 'A'].includes(el.tagName) && (e.key === ' ' || e.key === 'Enter')) return
  if (e.key === ' ') { e.preventDefault(); player.toggle() }
  else if (e.key === 'ArrowRight') player.seek(t.value + 5)
  else if (e.key === 'ArrowLeft') player.seek(t.value - 5)
  else if (e.key === ']') seekTurn(1)
  else if (e.key === '[') seekTurn(-1)
  else if (e.key.toLowerCase() === 'k') seekMoment(1)
  else if (e.key.toLowerCase() === 'j') seekMoment(-1)
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await loadCall()
  const q = route.query
  if (typeof q.t === 'string') player.seek(q.t === 'end' ? duration.value : Number(q.t) || 0)
  if ('read' in q) reading.value = true
  if ('play' in q) player.play()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

// ------------------------------------------------------------- the demo line
const otherLang = computed(() => (lang.value === 'fr' ? 'en' : 'fr'))
</script>

<template>
  <div class="landing">
    <header class="lp-top">
      <CvLogo />
      <nav :aria-label="c.navLabel" class="lp-nav">
        <a href="#hear">{{ c.nav[0] }}</a><a href="#said">{{ c.nav[1] }}</a><a href="#guards">{{ c.nav[2] }}</a>
      </nav>
      <div class="right">
        <UTabs v-model="langModel" :items="langItems" :content="false" size="xs" color="neutral" aria-label="Language / Langue" class="langtabs">
          <template #default="{ item }">
            <span :lang="item.value"><span class="long">{{ item.label }}</span><span class="short" aria-hidden="true">{{ item.short }}</span></span>
          </template>
        </UTabs>
        <UButton to="/sign-in" color="neutral" size="md" icon="i-lucide-log-in" :aria-label="c.signin" class="signin">
          <span class="signin-word">{{ c.signin }}</span>
        </UButton>
      </div>
    </header>

    <section class="hero" aria-labelledby="h1">
      <p class="eyebrow">
        <CvMark :size="22" />{{ c.eyebrow }}
      </p>
      <h1 id="h1">
        {{ c.h1 }}
      </h1>
      <p class="lede">
        {{ c.lede }}
      </p>
    </section>

    <div id="hear" class="stagewrap">
      <CallStage
        :turns="call.turns" :t="t" :duration="duration" :playing="playing" :items="filled" :route="call.route" :show-route="showRoute"
        :reading="reading" :copy="stageCopy" :lang="lang" @toggle="player.toggle()" @seek="player.seek($event)" @read="v => reading = v"
      />
      <p class="sr-only-cv" aria-live="polite">
        <template v-if="lastFinal && playing">
          {{ lastFinal.who === 'cv' ? c.stage.cv : c.stage.caller }}: {{ lastFinal.text }}
        </template>
      </p>
    </div>

    <section id="ring" class="ringband" aria-labelledby="ring-h">
      <NuxtLink :to="{ path: '/call', query: { lang } }" class="bigcall" :aria-label="c.ringBtns[0]">
        <span class="halo" aria-hidden="true" /><UIcon name="i-lucide-phone" />
      </NuxtLink>
      <div class="ringtext">
        <h2 id="ring-h">
          {{ c.ringH }}
        </h2>
        <p class="ringp">
          {{ c.ringP }}
        </p>
        <p class="ringcap">
          {{ c.ringTry }}
        </p>
        <p class="ringnote">
          <UIcon name="i-lucide-mic" class="size-4 shrink-0" />{{ c.ringNote }}
        </p>
        <div class="ringactions">
          <UButton :to="{ path: '/call', query: { lang } }" size="xl" icon="i-lucide-phone" :label="c.ringBtns[0]" />
          <UButton :to="{ path: '/call', query: { type: '1', lang } }" size="xl" color="neutral" variant="outline" icon="i-lucide-keyboard" :label="c.ringBtns[1]" />
          <UButton :to="{ path: '/call', query: { lang: otherLang } }" size="xl" color="neutral" variant="outline" icon="i-lucide-languages" :label="c.ringBtns[2]" :lang="otherLang" />
        </div>
      </div>
    </section>

    <section id="said" class="said" aria-labelledby="said-h">
      <h2 id="said-h">
        {{ c.saidH }}
      </h2>
      <ul class="rows">
        <li v-for="(r, i) in c.rows" :key="i" class="row">
          <p class="ask round">
            <CvMark :size="28" />{{ r.ask }}
          </p>
          <p class="quote" :class="{ caller: r.caller }">
            <small>{{ r.role }}</small>{{ r.line }}
          </p>
          <div class="pills">
            <CvTag v-if="r.tag && r.tag.kind === 'urgent'" kind="urgent" :icon="r.tag.icon">
              {{ r.tag.text }}
            </CvTag>
            <span v-for="p in r.pills" :key="p" class="heard plain"><UIcon name="i-lucide-check" class="size-3.5 text-jade-ink" />{{ p }}</span>
            <CvTag v-if="r.tag && r.tag.kind === 'fast'" kind="fast" :icon="r.tag.icon">
              {{ r.tag.text }}
            </CvTag>
          </div>
        </li>
      </ul>
    </section>

    <section id="guards" class="guards" aria-labelledby="guards-h">
      <h2 id="guards-h">
        {{ c.guardsH }}
      </h2>
      <ol>
        <li v-for="g in c.guards" :key="g.h" class="guard">
          <span class="gic" aria-hidden="true"><UIcon :name="g.icon" /></span>
          <h3>{{ g.h }}</h3>
          <p class="gp">
            {{ g.p }}
          </p>
          <p class="demo" :class="{ caller: g.caller }">
            {{ g.demo }}<template v-if="g.hush">
              <span class="hush">■■■■ {{ c.removed }}</span>{{ lang === 'fr' ? ' »' : '”' }}
            </template>
          </p>
        </li>
      </ol>
    </section>

    <p class="comply">
      {{ c.comply }}
    </p>
    <footer class="foot">
      <CvLogo />
      <span>{{ c.foot }}</span>
      <div class="right">
        <UButton to="/sign-in" color="neutral" variant="link" size="sm" :label="c.footLinks[0]" />
        <UButton color="primary" variant="link" size="sm" :label="c.footLinks[1]" :lang="otherLang" @click="prefs.lang.value = otherLang" />
        <UButton to="#guards" color="neutral" variant="link" size="sm" :label="c.footLinks[2]" />
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing { width: min(1280px, 100%); margin: 0 auto; padding: 0 40px; }
.lp-top { display: flex; align-items: center; gap: 22px; height: 84px; }
.lp-nav { display: flex; gap: 26px; margin-left: 28px; }
.lp-nav a { color: var(--cv-muted); text-decoration: none; font-weight: 500; font-size: 15px; }
.lp-nav a:hover { color: var(--cv-ink); }
.right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.langtabs { width: auto; }
.langtabs .short { display: none; }

/* The headline, centred and cushioned. */
.hero { display: grid; justify-items: center; text-align: center; padding: 22px 0 30px; }
.eyebrow { margin: 0 0 22px; display: inline-flex; align-items: center; gap: 10px; padding: 7px 16px 7px 10px; border-radius: 999px; background: var(--cv-surface); color: var(--cv-muted); font-size: 14px; box-shadow: var(--cv-shadow-soft); }
h1 { font-size: clamp(48px, 6.2vw, 88px); line-height: .96; font-weight: 900; letter-spacing: -0.035em; max-width: 15ch; }
.lede { margin: 20px 0 0; max-width: 66ch; color: var(--cv-muted); font-size: 18px; line-height: 1.55; }
.stagewrap { scroll-margin-top: 20px; }

/* Call the demo line */
.ringband { margin-top: 96px; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 32px 56px; align-items: center; padding: 56px; border-radius: 44px; background: var(--cv-jade-wash); }
.bigcall { position: relative; width: 184px; height: 184px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-jade); color: var(--cv-on-jade); font-size: 72px; box-shadow: inset 0 -8px 0 var(--cv-lip), 0 22px 44px -22px var(--cv-jade); transition: transform 200ms var(--ease-spring); }
.bigcall:hover { transform: translateY(-3px) rotate(-6deg); }
.bigcall:active { transform: translateY(2px); }
.bigcall .halo { position: absolute; inset: -10px; border-radius: 50%; border: 3px solid var(--cv-jade); animation: halo 2.2s var(--ease-tide) infinite; }
.ringtext { max-width: 760px; }
.ringband h2 { font-size: 52px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.02; }
.ringp { color: var(--cv-ink); max-width: 580px; font-size: 17px; margin: 14px 0 0; }
.ringcap { margin: 20px 0 0; display: inline-block; padding: 14px 20px; border-radius: 24px 24px 6px 24px; background: var(--cv-sand); font-family: var(--font-round); font-size: 22px; font-weight: 800; line-height: 1.3; letter-spacing: -0.01em; max-width: 640px; }
.ringnote { display: flex; align-items: flex-start; gap: 8px; margin: 20px 0 0; font-size: 14px; color: var(--cv-muted); max-width: 580px; }
.ringnote :deep(svg), .ringnote > span:first-child { margin-top: 3px; }
.ringactions { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }

/* What your team gets: three asked-and-answered rows. */
.said { margin-top: 104px; }
.said h2, .guards h2 { font-size: 52px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.02; max-width: 16ch; }
.rows { list-style: none; margin: 32px 0 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.row { display: grid; gap: 14px; align-content: start; padding: 24px; border-radius: 32px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.ask { margin: 0; display: flex; align-items: center; gap: 10px; font-size: 21px; font-weight: 900; line-height: 1.15; }
.quote { margin: 0; padding: 14px 18px; border-radius: 6px 24px 24px 24px; background: var(--cv-jade-wash); font-size: 17px; line-height: 1.45; }
.quote.caller { border-radius: 24px 6px 24px 24px; background: var(--cv-sand); }
.quote small { display: block; font-size: 12.5px; font-weight: 600; color: var(--cv-jade-ink); margin-bottom: 4px; }
.quote.caller small { color: var(--cv-caller); }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pills .heard { gap: 6px; padding-left: 10px; font-size: 13.5px; }

/* Safeguards */
.guards { margin-top: 104px; }
.guards ol { list-style: none; margin: 32px 0 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.guard { display: grid; gap: 10px; align-content: start; padding: 26px 24px; border-radius: 32px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.gic { width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-jade); color: var(--cv-on-jade); font-size: 26px; box-shadow: inset 0 -4px 0 var(--cv-lip); }
.guard h3 { font-size: 25px; font-weight: 900; line-height: 1.12; }
.gp { margin: 0; color: var(--cv-muted); font-size: 15px; }
.demo { margin: 6px 0 0; justify-self: start; padding: 12px 16px; border-radius: 6px 22px 22px 22px; background: var(--cv-jade-wash); font-size: 16px; line-height: 1.4; }
.demo.caller { background: var(--cv-sand); border-radius: 22px 6px 22px 22px; }
.demo .hush { margin-left: 6px; }

.comply { margin: 72px auto 0; max-width: 72ch; text-align: center; color: var(--cv-muted); font-size: 14.5px; }
.foot { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-top: 40px; padding: 26px 0 40px; border-top: 2px solid var(--cv-sunk); color: var(--cv-muted); font-size: 14px; }
.foot .right { gap: 6px; }

@media (max-width: 1100px) {
  .lp-nav { gap: 18px; margin-left: 12px; }
  .rows, .guards ol { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 900px) {
  .lp-nav { display: none; }
}
@media (max-width: 720px) {
  .landing { padding: 0 16px; }
  .lp-top { height: 64px; gap: 12px; }
  .langtabs .long, .signin-word { display: none; }
  .langtabs .short { display: inline; }
  .hero { padding: 18px 0 22px; }
  .eyebrow { font-size: 12.5px; margin-bottom: 16px; text-align: left; border-radius: 22px; }
  h1 { font-size: 46px; }
  .lede { font-size: 16px; margin-top: 18px; }
  .ringband { margin-top: 56px; padding: 28px 18px; grid-template-columns: minmax(0, 1fr); justify-items: start; gap: 18px; border-radius: 30px; }
  .bigcall { width: 112px; height: 112px; font-size: 44px; }
  .ringband h2, .said h2, .guards h2 { font-size: 34px; }
  .ringcap { font-size: 18px; }
  .said, .guards { margin-top: 64px; }
  .row, .guard { padding: 18px; border-radius: 26px; }
  .comply { margin-top: 48px; text-align: left; }
}
</style>
