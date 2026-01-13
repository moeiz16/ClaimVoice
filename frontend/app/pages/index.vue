<script setup lang="ts">
// The landing page is a call you can hear, and the tape is the hero. Before play, ClaimVoice's own first line is
// written above the line and the caller's teaser below it, with the whole call drawn as the horizon between them.
// Pressing play writes the words being said on the tape (Larkspur above, the caller below) and fills the claim file
// beneath it: values fly from the words into their boxes, the card number is hushed, and the route unfurls at the
// end. Then the demo line, what each person gets, the safeguards and the compliance line. Nothing auto-plays.
// Query flags for review: ?t=<s>|end, ?play, ?read (and ?still, ?theme, applied app-wide).
import { builtInCall, horizonBars, noticeItems, parseLandingCall, slipAt, type LandingCall } from '~/utils/landingCall'
import { STEPS } from '~/utils/notice'
import { fmtClock, fmtDurationWords } from '~/utils/format'
import { stripCardToken, turnAt } from '~/utils/transcript'

definePageMeta({ layout: 'public' })

const prefs = usePrefs()
const lang = computed<'en' | 'fr'>(() => (prefs.lang.value === 'fr' ? 'fr' : 'en'))
const route = useRoute()

const COPY = {
  en: {
    nav: ['Ring the demo line', 'What your team gets', 'Safeguards'],
    navLabel: 'Sections',
    signin: 'Supervisors, sign in',
    eyebrow: 'A claim call to Larkspur Mutual, Calgary · Thursday 8 January, 2:14 a.m., during a Chinook windstorm',
    sample: 'Sample call, shortened · voices are synthetic',
    tape: 'The sample call',
    h1a: 'Tell me what happened.',
    h1b: 'I\'ll take it from there.',
    teaserWho: 'Dana, policyholder',
    teaser: '“The wind just smashed our skylight.”',
    lede: 'ClaimVoice answers your claims line at any hour, in English or French. It takes the first report, asks the right follow-up questions, and hands your team a claim file where every detail links back to the words it came from.',
    names: { cv: 'ClaimVoice', caller: 'Dana, policyholder' },
    removed: 'removed',
    horizon: { play: 'Play the call', pause: 'Pause the call', playLabel: 'Play the call', playSub: '', paused: 'Recording paused · card number', wave: 'Recording of the call. Click to move through it. Moments:', moments: 'Moments in the call', jump: 'jump here' },
    slip: { label: 'Claim file', empty: 'Fills in here as each detail is heard.', fromPolicy: 'from the policy' },
    notice: {
      pending: 'Not heard yet',
      heardAt: 'Heard at',
      steps: [...STEPS] as string[],
      boxes: {
        consent: 'Recording consent', policy: 'Policy and policyholder', where: 'Insured address', hurt: 'Anyone hurt',
        skylight: 'Damage', debris: 'Cause', when: 'When it happened', photos: 'Photos', card: 'Deductible payment',
        readback: 'Read back to the caller', claimno: 'Claim number',
      } as Record<string, string>,
      other: 'Also heard',
      states: { done: 'Complete', current: 'Filling in', waiting: 'Not reached yet', open: 'Still open' },
      stepOf: 'Step {n} of 7',
      allDone: 'Every step of the call is done',
      whereTitle: 'Where it goes',
      whereLabel: 'Route, with three reasons',
      wherePending: 'Decided when the call ends',
    },
    readBack: 'Read back, the caller agreed',
    captions: 'Captions', read: 'Read instead',
    legendCv: 'ClaimVoice, above the line', legendCaller: 'Caller, below',
    ringSmall: ['Or talk to it yourself.', 'Works in this browser, no app.'],
    ringH: 'Ring the demo line',
    ringP: 'Pretend something has just happened to your car or your home. ClaimVoice will take the claim, live, in this browser.',
    ringTry: 'Try: “Someone backed into my car in the Chinook Centre parking lot.”',
    ringBtns: ['Ring the demo line', 'Type instead', 'Appeler en français'],
    ringNote: 'Uses your microphone in this browser only. Nothing you say is kept after you close the page.',
    saidH: 'What the caller hears, and what your team gets.',
    rows: [
      { role: 'Policyholder', line: '“Is everyone safe right now? Then let\'s get your claim started. It takes about four minutes.”', caller: false, gets: 'They get', pills: ['A claim number before hanging up', 'A photo link by text', 'A time someone will call'], tag: null as null | { kind: 'urgent' | 'fast', icon: string, text: string } },
      { role: 'Intake team', line: '“The wind tore the cover off my gas meter and I can smell gas.”', caller: true, gets: 'You get', pills: ['The caller told to leave and call 911', 'A summary, so nobody asks twice'], tag: { kind: 'urgent' as const, icon: 'i-lucide-triangle-alert', text: 'Urgent safety, waiting for a person' } },
      { role: 'Adjuster', line: '“Here\'s what I have. Is that right?”', caller: false, gets: 'You get', pills: ['Every detail linked to the words it came from', 'The recording, by speaker'], tag: { kind: 'fast' as const, icon: 'i-lucide-check', text: 'A route, with reasons in plain words' } },
    ],
    guardsLabel: 'Safeguards',
    guards: [
      { icon: 'i-lucide-shield-check', h: 'Recording consent comes first', p: 'Every call opens by asking. Where both people must agree to be recorded, nothing is kept until the caller says yes.', demo: '“This call is recorded so we get your claim right. Is that okay?”', hush: false, caller: false },
      { icon: 'i-lucide-credit-card', h: 'Card numbers are never taken', p: 'If a caller starts reading a card number, ClaimVoice stops them, and that moment is cut from the recording and the transcript.', demo: '“It\'s four-five', hush: true, caller: true },
      { icon: 'i-lucide-user-round', h: 'A person can take over any call', p: 'Callers can ask for a person at any time. Supervisors can listen, pass ClaimVoice a note, or take the call. Nothing is ever denied automatically.', demo: '“Of course. I\'m bringing in Renée now.”', hush: false, caller: false },
    ],
    comply: 'Designed to support the NAIC model bulletin on insurers\' use of AI, state call-recording consent rules, PCI DSS, GLBA, PIPEDA and Québec\'s Law 25. In English and French.',
    foot: 'Built for claims teams at regional insurers and agencies.',
    footLinks: ['Supervisors, sign in', 'Français', 'Privacy'],
    readLabel: 'The whole call, as text',
  },
  fr: {
    nav: ['Appeler la ligne de démo', 'Ce que votre équipe reçoit', 'Garanties'],
    navLabel: 'Sections',
    signin: 'Superviseurs, connexion',
    eyebrow: 'Un appel de réclamation à Larkspur Mutual, Calgary · jeudi 8 janvier, 2 h 14, pendant une tempête de vent chinook',
    sample: 'Appel d\'exemple, abrégé · voix synthétiques',
    tape: 'L\'appel d\'exemple',
    h1a: 'Dites-moi ce qui s\'est passé.',
    h1b: 'Je m\'occupe du reste.',
    teaserWho: 'Dana, assurée',
    teaser: '« Le vent vient de briser notre puits de lumière. »',
    lede: 'ClaimVoice répond à votre ligne de réclamations à toute heure, en français ou en anglais. Il prend la première déclaration, pose les bonnes questions et remet à votre équipe un dossier où chaque détail renvoie aux mots d\'où il vient.',
    names: { cv: 'ClaimVoice', caller: 'Dana, assurée' },
    removed: 'retiré',
    horizon: { play: 'Écouter l\'appel', pause: 'Mettre en pause', playLabel: 'Écouter l\'appel', playSub: '', paused: 'Enregistrement en pause · numéro de carte', wave: 'Enregistrement de l\'appel. Cliquez pour vous déplacer. Moments :', moments: 'Moments de l\'appel', jump: 'aller ici' },
    slip: { label: 'Dossier', empty: 'Se remplit ici à mesure que chaque détail est entendu.', fromPolicy: 'selon la police' },
    notice: {
      pending: 'Pas encore entendu',
      heardAt: 'Entendu à',
      steps: ['Consentement', 'Police', 'Sécurité', 'Ce qui s\'est passé', 'Photos', 'Couverture', 'Relecture'],
      boxes: {
        consent: 'Consentement à l\'enregistrement', policy: 'Police et titulaire', where: 'Adresse assurée', hurt: 'Personnes blessées',
        skylight: 'Dommages', debris: 'Cause', when: 'Quand c\'est arrivé', photos: 'Photos', card: 'Paiement de la franchise',
        readback: 'Relu à l\'appelante', claimno: 'Numéro de réclamation',
      } as Record<string, string>,
      other: 'Aussi entendu',
      states: { done: 'Complète', current: 'En cours', waiting: 'Pas encore', open: 'Encore ouverte' },
      stepOf: 'Étape {n} sur 7',
      allDone: 'Toutes les étapes de l\'appel sont faites',
      whereTitle: 'Où va la réclamation',
      whereLabel: 'Acheminement, avec trois raisons',
      wherePending: 'Décidé à la fin de l\'appel',
    },
    readBack: 'Relu, l\'appelante est d\'accord',
    captions: 'Sous-titres', read: 'Lire plutôt',
    legendCv: 'ClaimVoice, au-dessus de la ligne', legendCaller: 'Appelant, en dessous',
    ringSmall: ['Ou parlez-lui vous-même.', 'Dans ce navigateur, sans appli.'],
    ringH: 'Appeler la ligne de démo',
    ringP: 'Imaginez qu\'il vient d\'arriver quelque chose à votre auto ou à votre maison. ClaimVoice prendra la réclamation, en direct, dans ce navigateur.',
    ringTry: 'Essayez : « Quelqu\'un a reculé dans mon auto au stationnement du Carrefour Laval. »',
    ringBtns: ['Appeler la ligne de démo', 'Écrire plutôt', 'Call in English'],
    ringNote: 'Utilise votre micro dans ce navigateur seulement. Rien de ce que vous dites n\'est gardé après la fermeture de la page.',
    saidH: 'Ce que l\'appelant entend, et ce que votre équipe reçoit.',
    rows: [
      { role: 'Assuré', line: '« Est-ce que tout le monde est en sécurité? Alors, commençons votre réclamation. Ça prend environ quatre minutes. »', caller: false, gets: 'Ils reçoivent', pills: ['Un numéro de réclamation avant de raccrocher', 'Un lien pour photos par texto', 'L\'heure où on les rappellera'], tag: null as null | { kind: 'urgent' | 'fast', icon: string, text: string } },
      { role: 'Équipe d\'accueil', line: '« Le vent a arraché le couvercle de mon compteur de gaz et ça sent le gaz. »', caller: true, gets: 'Vous recevez', pills: ['L\'appelant invité à sortir et à faire le 911', 'Un résumé, pour ne rien redemander'], tag: { kind: 'urgent' as const, icon: 'i-lucide-triangle-alert', text: 'Sécurité urgente, attend une personne' } },
      { role: 'Expert en sinistres', line: '« Voici ce que j\'ai. C\'est bien ça? »', caller: false, gets: 'Vous recevez', pills: ['Chaque détail relié aux mots d\'où il vient', 'L\'enregistrement, par voix'], tag: { kind: 'fast' as const, icon: 'i-lucide-check', text: 'Un acheminement, avec des raisons claires' } },
    ],
    guardsLabel: 'Garanties',
    guards: [
      { icon: 'i-lucide-shield-check', h: 'Le consentement d\'abord', p: 'Chaque appel commence par la question. Là où les deux personnes doivent accepter, rien n\'est gardé avant le oui de l\'appelant.', demo: '« L\'appel est enregistré pour bien traiter votre réclamation. Ça vous convient? »', hush: false, caller: false },
      { icon: 'i-lucide-credit-card', h: 'Jamais de numéro de carte', p: 'Si un appelant commence à lire un numéro de carte, ClaimVoice l\'arrête, et ce moment est retiré de l\'enregistrement et de la transcription.', demo: '« C\'est quatre-cinq', hush: true, caller: true },
      { icon: 'i-lucide-user-round', h: 'Une personne peut prendre l\'appel', p: 'L\'appelant peut demander une personne en tout temps. Les superviseurs peuvent écouter, glisser une note à ClaimVoice ou prendre l\'appel. Rien n\'est jamais refusé automatiquement.', demo: '« Bien sûr. Je fais venir Renée. »', hush: false, caller: false },
    ],
    comply: 'Conçu pour soutenir le bulletin type de la NAIC sur l\'usage de l\'IA par les assureurs, les règles de consentement à l\'enregistrement, PCI DSS, GLBA, la LPRPDE et la Loi 25 du Québec. En français et en anglais.',
    foot: 'Conçu pour les équipes de réclamations des assureurs et cabinets régionaux.',
    footLinks: ['Superviseurs, connexion', 'English', 'Confidentialité'],
    readLabel: 'Tout l\'appel, en texte',
  },
}
const c = computed(() => COPY[lang.value])
useHead(() => ({ title: lang.value === 'fr' ? 'ClaimVoice · la ligne de réclamations qui écoute d\'abord' : 'ClaimVoice · the claims line that listens first', htmlAttrs: { lang: lang.value } }))

// ------------------------------------------------------------- language and view switches (Nuxt UI tabs)
const langItems = [{ label: 'English', short: 'EN', value: 'en' }, { label: 'Français', short: 'FR', value: 'fr' }]
const langModel = computed<string>({
  get: () => lang.value,
  set: (v) => { prefs.lang.value = v === 'fr' ? 'fr' : 'en' },
})
const reading = ref(false)
const viewItems = computed(() => [
  { label: c.value.captions, value: 'captions', icon: 'i-lucide-captions' },
  { label: c.value.read, value: 'read', icon: 'i-lucide-scroll-text' },
])
const viewModel = computed<string>({
  get: () => (reading.value ? 'read' : 'captions'),
  set: (v) => { reading.value = v === 'read' },
})

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

const bars = computed(() => horizonBars(call.value))
const idx = computed(() => turnAt(call.value.turns, t.value))
const started = computed(() => t.value > 0.05 || playing.value)
const hushing = computed(() => call.value.turns.some(x => x.hush != null && t.value >= x.hush && t.value < x.to + 1.9))
const allItems = computed(() => noticeItems(call.value, c.value.readBack))
const filled = computed(() => slipAt(allItems.value, t.value))
const showRoute = computed(() => t.value >= duration.value - 0.05)
const durationWords = computed(() => fmtDurationWords(duration.value, lang.value))
const horizonCopy = computed(() => ({ ...c.value.horizon, playSub: `${durationWords.value} · ${lang.value === 'fr' ? 'sous-titres activés' : 'captions on'}` }))
const noticeCopy = computed(() => ({ ...c.value.notice, title: c.value.slip.label, empty: c.value.slip.empty, fromPolicy: c.value.slip.fromPolicy }))
const finished = computed(() => call.value.turns.filter(x => x.to <= t.value))
const lastFinal = computed(() => {
  const f = finished.value[finished.value.length - 1]
  return f ? { ...f, text: stripCardToken(f.text) } : null
})
const callerShort = computed(() => c.value.names.caller.split(',')[0] ?? c.value.names.caller)

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
const phone = useMediaQuery('(max-width: 720px)')
</script>

<template>
  <div class="landing">
    <header class="lp-top">
      <CvLogo />
      <nav :aria-label="c.navLabel" class="lp-nav">
        <a href="#ring">{{ c.nav[0] }}</a><a href="#said">{{ c.nav[1] }}</a><a href="#guards">{{ c.nav[2] }}</a>
      </nav>
      <div class="right">
        <UTabs v-model="langModel" :items="langItems" :content="false" variant="pill" size="xs" color="neutral" aria-label="Language / Langue" class="langtabs">
          <template #default="{ item }">
            <span :lang="item.value"><span class="long">{{ item.label }}</span><span class="short" aria-hidden="true">{{ item.short }}</span></span>
          </template>
        </UTabs>
        <UButton to="/sign-in" color="neutral" variant="link" size="md" icon="i-lucide-log-in" :aria-label="c.signin" class="signin">
          <span class="signin-word">{{ c.signin }}</span>
        </UButton>
      </div>
    </header>

    <div class="eyebrow">
      <span class="dot" aria-hidden="true" /><span>{{ c.eyebrow }}</span>
      <UBadge color="neutral" variant="soft" size="md" class="sample">
        {{ c.sample }}
      </UBadge>
    </div>

    <Tape class="hero" :label="c.tape">
      <template #above>
        <div class="words up" :class="{ reading }">
          <div class="headline" :class="{ gone: started || reading }">
            <h1>{{ c.h1a }} <em>{{ c.h1b }}</em></h1>
          </div>
          <LyricSheet v-if="started && !reading" :turns="call.turns" :t="t" side="cv" :name="c.names.cv" :removed="c.removed" :lang="lang" />
        </div>
      </template>

      <HorizonWave
        :bars="bars" :duration="duration" :t="t" :playing="playing" :turn-index="idx" :moments="call.moments"
        :hushing="hushing" :copy="horizonCopy" @toggle="player.toggle()" @seek="player.seek($event)"
      />

      <template #below>
        <div v-if="!reading" class="words down">
          <p class="teaser" :class="{ gone: started }">
            <small>{{ c.teaserWho }}</small>{{ c.teaser }}
          </p>
          <LyricSheet v-if="started" :turns="call.turns" :t="t" side="caller" :name="c.names.caller" :removed="c.removed" :lang="lang" />
        </div>
        <ol v-else class="readlist" :aria-label="c.readLabel">
          <li v-for="(x, i) in call.turns" :key="i" :class="[x.who, { cur: i === idx && started }]">
            <button type="button" class="tm num" :aria-label="`${fmtClock(x.from)}, ${x.who === 'cv' ? c.names.cv : callerShort}`" @click="player.seek(x.from)">
              {{ fmtClock(x.from) }}
            </button>
            <b>{{ x.who === 'cv' ? c.names.cv : callerShort }}</b>
            <span class="said">{{ stripCardToken(x.text) }}<template v-if="x.hush != null"> <span class="hush">■■■■ {{ c.removed }}</span></template></span>
          </li>
        </ol>
        <p class="sr-only-cv" aria-live="polite">
          <template v-if="lastFinal && playing">
            {{ lastFinal.who === 'cv' ? c.names.cv : c.names.caller }}: {{ lastFinal.text }}
          </template>
        </p>
      </template>

      <template #foot>
        <div class="controls">
          <time class="num clock">{{ fmtClock(t) }} / {{ fmtClock(duration) }}</time>
          <UTabs v-model="viewModel" :items="viewItems" :content="false" variant="pill" size="sm" color="neutral" :aria-label="c.captions" />
          <div class="legend" aria-hidden="true">
            <span><i />{{ c.legendCv }}</span><span class="cl"><i />{{ c.legendCaller }}</span>
          </div>
          <div class="ring-cta">
            <small>{{ c.ringSmall[0] }}<br>{{ c.ringSmall[1] }}</small>
            <UButton to="#ring" color="neutral" variant="soft" icon="i-lucide-phone" :label="c.ringH" />
          </div>
        </div>
      </template>
    </Tape>

    <p class="lede">
      {{ c.lede }}
    </p>

    <LandingNotice
      :items="filled" :turns="call.turns" :route="call.route" :show-route="showRoute" :started="started" :animate="playing"
      :copy="noticeCopy" :lang="lang" @seek="player.seek($event)"
    />

    <section id="ring" class="ringband" aria-labelledby="ring-h">
      <div class="orbwrap">
        <DemoOrb state="idle" :size="phone ? 128 : 176" />
      </div>
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
          <UButton :to="{ path: '/call', query: { lang } }" color="primary" icon="i-lucide-mic" :label="c.ringBtns[0]" />
          <UButton :to="{ path: '/call', query: { type: '1', lang } }" color="neutral" variant="soft" icon="i-lucide-keyboard" :label="c.ringBtns[1]" class="on-wash" />
          <UButton :to="{ path: '/call', query: { lang: otherLang } }" color="neutral" variant="soft" icon="i-lucide-languages" :label="c.ringBtns[2]" :lang="otherLang" class="on-wash" />
        </div>
      </div>
    </section>

    <section id="said" class="said" aria-labelledby="said-h">
      <h2 id="said-h">
        {{ c.saidH }}
      </h2>
      <ul class="rows">
        <li v-for="(r, i) in c.rows" :key="i" class="row fade-scroll">
          <div class="say">
            <span class="role">{{ r.role }}</span>
            <p class="quote" :class="{ caller: r.caller }">
              {{ r.line }}
            </p>
          </div>
          <div class="gets">
            <span class="label">{{ r.gets }}</span>
            <div class="pills">
              <CvTag v-if="r.tag && r.tag.kind === 'urgent'" kind="urgent" :icon="r.tag.icon">
                {{ r.tag.text }}
              </CvTag>
              <span v-for="p in r.pills" :key="p" class="heard plain">{{ p }}</span>
              <CvTag v-if="r.tag && r.tag.kind === 'fast'" kind="fast" :icon="r.tag.icon">
                {{ r.tag.text }}
              </CvTag>
            </div>
          </div>
        </li>
      </ul>
    </section>

    <section id="guards" class="guards" :aria-label="c.guardsLabel">
      <ol>
        <li v-for="(g, i) in c.guards" :key="g.h" class="guard fade-scroll">
          <span class="no num" aria-hidden="true">{{ i + 1 }}</span>
          <div class="gtext">
            <h3><UIcon :name="g.icon" class="gicon" />{{ g.h }}</h3>
            <p>{{ g.p }}</p>
          </div>
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
/* ------------------------------------------------------------ top: a quiet line, then the eyebrow */
.lp-top { display: flex; align-items: center; gap: 22px; height: 68px; padding: 0 32px; }
.lp-nav { display: flex; gap: 24px; margin-left: 28px; }
.lp-nav a { color: var(--cv-muted); text-decoration: none; font-weight: 600; font-size: 14.5px; }
.lp-nav a:hover { color: var(--cv-ink); }
.right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.langtabs { width: auto; }
.langtabs .short { display: none; }
.signin { font-weight: 650; }

.eyebrow { padding: 4px 32px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; color: var(--cv-muted); font-size: 14px; font-weight: 550; }
.eyebrow .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); flex: none; }
.eyebrow .sample { margin-left: 4px; }

/* ------------------------------------------------------------ the tape, as the hero */
.tape.hero { padding-top: 26px; padding-bottom: 14px; border-top: 1px solid var(--cv-rule); }
.hero :deep(.line) { height: auto; }
.words { display: grid; }
.words > * { grid-area: 1 / 1; min-height: 0; }
.words.up { height: 236px; }
.words.up.reading { height: 0; overflow: hidden; }
.words.down { height: 156px; }
.headline { display: flex; flex-direction: column; justify-content: flex-end; padding-bottom: 6px; transition: opacity 400ms var(--ease-voice), transform 400ms var(--ease-voice); }
.headline h1 { font-size: clamp(44px, 6.2vw, 90px); line-height: .98; font-weight: 720; letter-spacing: -0.035em; max-width: 1040px; }
.headline h1 em { display: block; font-style: normal; color: var(--cv-orchid); }
.teaser {
  margin: 0; padding-top: 6px; justify-self: end; max-width: 520px; text-align: right; color: var(--cv-caller);
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 30px; font-weight: 600; line-height: 1.15; letter-spacing: -0.015em;
  transition: opacity 400ms var(--ease-voice), transform 400ms var(--ease-voice);
}
.teaser small { display: block; font-family: var(--font-sans); font-variation-settings: normal; font-size: 13px; font-weight: 650; color: var(--cv-muted); letter-spacing: 0; margin-bottom: 4px; }
/* Pressing play: the headline lifts away and the teaser sinks; both stay readable to assistive technology. */
.headline.gone { opacity: 0; transform: translateY(-24px); pointer-events: none; }
.teaser.gone { opacity: 0; transform: translateY(16px); pointer-events: none; }

.readlist { list-style: none; margin: 4px 0 0; padding: 0; display: grid; gap: 2px; text-align: left; max-height: 440px; overflow: auto; font-family: var(--font-sans); font-variation-settings: normal; font-weight: 400; letter-spacing: 0; color: var(--cv-ink); }
.readlist li { display: grid; grid-template-columns: 56px 130px minmax(0, 1fr); gap: 10px; padding: 6px 8px; border-radius: 6px; font-size: calc(15.5px * var(--cv-caption-scale)); line-height: 1.55; border-bottom: 1px solid var(--cv-rule); }
.readlist li.cur { background: var(--cv-orchid-wash); }
.readlist li.caller b, .readlist li.caller .said { color: var(--cv-caller); }
.readlist b { font-weight: 650; }
.readlist .tm { border: 0; background: none; color: var(--cv-muted); text-align: left; padding: 0; font-weight: 600; font-size: 14px; }
.readlist .tm:hover { color: var(--cv-orchid-ink); }

.controls { display: flex; align-items: center; gap: 12px 16px; flex-wrap: wrap; border-top: 1px solid var(--cv-rule); padding-top: 12px; }
.clock { font-weight: 650; font-size: 14px; color: var(--cv-muted); min-width: 92px; }
.controls :deep([role="tablist"]) { width: auto; }
.legend { display: flex; gap: 14px; font-size: 12.5px; font-weight: 650; color: var(--cv-muted); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 4px; height: 14px; border-radius: 2px; background: var(--cv-orchid); display: inline-block; }
.legend .cl i { background: var(--cv-caller); }
.ring-cta { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.ring-cta small { color: var(--cv-muted); font-size: 13px; text-align: right; line-height: 1.35; }

.lede { margin: 0; padding: 20px 32px 4px; max-width: calc(640px + 64px); color: var(--cv-muted); font-size: 17px; line-height: 1.55; }

/* ------------------------------------------------------------ ring the demo line */
.ringband {
  margin: 64px 0 0; padding: 64px 32px 72px; background: var(--cv-orchid-wash); border-block: 1px solid var(--cv-rule);
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 32px 56px; align-items: center;
}
.orbwrap { padding: 18px; }
.ringtext { max-width: 760px; }
.ringband h2 { font-size: 54px; font-weight: 740; letter-spacing: -0.035em; line-height: 1.02; }
.ringp { color: var(--cv-muted); max-width: 580px; font-size: 17px; margin: 12px 0 0; }
.ringcap { margin: 22px 0 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 26px; font-weight: 600; color: var(--cv-caller); line-height: 1.25; letter-spacing: -0.015em; max-width: 680px; }
.ringnote { display: flex; align-items: flex-start; gap: 8px; margin: 22px 0 0; font-size: 14px; color: var(--cv-muted); max-width: 580px; }
.ringnote :deep(svg), .ringnote > span:first-child { margin-top: 3px; }
.ringactions { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.on-wash { background: var(--cv-surface); }
.on-wash:hover { background: var(--cv-sunk); }

/* ------------------------------------------------------------ said → filed: three ruled rows */
.said { padding: 88px 32px 32px; }
.said h2 { font-size: 44px; font-weight: 740; letter-spacing: -0.03em; max-width: 820px; line-height: 1.06; }
.rows { list-style: none; margin: 32px 0 0; padding: 0; border-bottom: 1px solid var(--cv-rule); }
.row { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 16px 48px; align-items: start; padding: 28px 0; border-top: 1px solid var(--cv-rule); }
.role { display: block; font-weight: 650; font-size: 13.5px; color: var(--cv-muted); margin-bottom: 6px; }
.quote { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 27px; font-weight: 600; line-height: 1.2; letter-spacing: -0.015em; color: var(--cv-ink); }
.quote.caller { color: var(--cv-caller); }
.gets { padding-top: 2px; }
.gets .label { display: block; margin-bottom: 8px; }
.pills { display: flex; flex-wrap: wrap; gap: 8px; }
.fade-scroll { animation: rise-in linear both; animation-timeline: view(); animation-range: entry 0% entry 40%; }
@media (prefers-reduced-motion: reduce) { .fade-scroll { animation: none; } }
:global(:root.reduce-motion) .fade-scroll { animation: none; }

/* ------------------------------------------------------------ safeguards: a numbered list */
.guards { padding: 56px 32px 24px; }
.guards ol { list-style: none; margin: 0; padding: 0; border-bottom: 1px solid var(--cv-rule); }
.guard { display: grid; grid-template-columns: 44px minmax(0, 1.1fr) minmax(0, 1fr); gap: 12px 32px; align-items: start; padding: 26px 0; border-top: 1px solid var(--cv-rule); }
.guard .no {
  width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-ink); color: var(--cv-bg);
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 16px;
}
.guard h3 { display: flex; align-items: center; gap: 10px; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
.gicon { width: 22px; height: 22px; color: var(--cv-orchid-ink); flex: none; }
.gtext p { color: var(--cv-muted); margin: 8px 0 0; max-width: 560px; }
.demo { margin: 0; padding-top: 2px; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 20px; font-weight: 600; line-height: 1.3; color: var(--cv-ink); }
.demo.caller { color: var(--cv-caller); }
.demo .hush { margin-left: 6px; }

/* ------------------------------------------------------------ compliance + footer */
.comply { margin: 0; padding: 28px 32px 32px; max-width: calc(860px + 64px); color: var(--cv-muted); font-size: 14.5px; }
.foot { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; padding: 22px 32px 36px; border-top: 1px solid var(--cv-rule); color: var(--cv-muted); font-size: 13.5px; }
.foot .right { gap: 6px; }

@media (max-width: 1100px) {
  .words.up { height: 216px; }
  .teaser { font-size: 25px; }
  .lp-nav { gap: 18px; margin-left: 12px; }
  .ring-cta small { display: none; }
}
@media (max-width: 900px) {
  .lp-nav { display: none; }
}
@media (max-width: 720px) {
  .lp-top { padding: 0 16px; height: 60px; gap: 12px; }
  .langtabs .long, .signin-word { display: none; }
  .langtabs .short { display: inline; }
  .eyebrow { padding: 2px 16px 12px; font-size: 12.5px; display: block; line-height: 1.5; }
  .eyebrow .dot { display: inline-block; margin-right: 8px; vertical-align: 1px; }
  .eyebrow .sample { display: table; margin: 6px 0 0; font-size: 12px; }
  .tape.hero { padding-top: 18px; }
  .words.up { height: 228px; }
  .words.down { height: 132px; }
  .teaser { font-size: 21px; max-width: 92%; }
  .readlist li { grid-template-columns: 44px minmax(0, 1fr); gap: 2px 10px; }
  .readlist li b, .readlist li .said { grid-column: 2; }
  .legend { display: none; }
  .ring-cta { margin-left: 0; }
  .lede { padding: 16px 16px 0; font-size: 15.5px; }
  .ringband { margin-top: 48px; padding: 48px 16px 56px; grid-template-columns: minmax(0, 1fr); justify-items: start; gap: 18px; }
  .orbwrap { padding: 10px; }
  .ringband h2 { font-size: 34px; }
  .ringcap { font-size: 21px; }
  .said { padding: 64px 16px 24px; }
  .said h2 { font-size: 30px; }
  .row { grid-template-columns: minmax(0, 1fr); padding: 22px 0; }
  .quote { font-size: 22px; }
  .guards { padding: 40px 16px 16px; }
  .guard { grid-template-columns: 36px minmax(0, 1fr); gap: 10px 14px; }
  .guard .demo { grid-column: 2; font-size: 18px; }
  .guard h3 { font-size: 20px; }
  .comply { padding: 24px 16px; }
  .foot { padding: 20px 16px 28px; }
  .foot .right { margin-left: 0; flex-wrap: wrap; }
}
</style>
