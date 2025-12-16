<script setup lang="ts">
// The landing page is a call you can hear (DESIGN.md §4): ClaimVoice's own first line as the headline, the whole
// call as a horizon you press play on, lyric captions in two alignments, values plucked into the claim slip, the
// card-number hush, and the route unfurling at the end. Nothing auto-plays. Query flags for review: ?t=<s>|end,
// ?play, ?read.
import { builtInCall, horizonBars, parseLandingCall, slipAt, type LandingCall } from '~/utils/landingCall'
import { fmtClock, fmtDurationWords } from '~/utils/format'
import { stripCardToken, turnAt } from '~/utils/transcript'

definePageMeta({ layout: 'public' })

const prefs = usePrefs()
const lang = computed<'en' | 'fr'>(() => (prefs.lang.value === 'fr' ? 'fr' : 'en'))
const route = useRoute()

const COPY = {
  en: {
    nav: ['Ring the demo line', 'What your team gets', 'Safeguards'],
    signin: 'Supervisors, sign in',
    eyebrow: 'A claim call to Larkspur Mutual, Calgary · Thursday 8 January, 2:14 a.m., during a Chinook windstorm',
    sample: 'Sample call, voices are synthetic',
    h1a: 'Tell me what happened.',
    h1b: 'I\'ll take it from there.',
    teaserWho: 'Dana, policyholder',
    teaser: '“The wind just smashed our skylight.”',
    lede: 'ClaimVoice answers your claims line at any hour, in English or French. It takes the first report, asks the right follow-up questions, and hands your team a claim file where every detail links back to the words it came from.',
    names: { cv: 'ClaimVoice', caller: 'Dana, policyholder' },
    removed: 'removed',
    horizon: { play: 'Play the call', pause: 'Pause the call', playLabel: 'Play the call', playSub: '', paused: 'Recording paused · card number', wave: 'Recording of the call. Click to move through it. Moments:', moments: 'Moments in the call' },
    slip: { label: 'Claim file', empty: 'Fills in here as each detail is heard.', fromPolicy: 'from the policy' },
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
      { role: 'Intake team', line: '“The wind tore the cover off my gas meter and I can smell gas.”', caller: true, gets: 'You get', pills: ['The caller told to leave and call 911', 'A summary, so nobody asks twice'], tag: { kind: 'urgent' as const, icon: 'urgent', text: 'Urgent safety, waiting for a person' } },
      { role: 'Adjuster', line: '“Here\'s what I have. Is that right?”', caller: false, gets: 'You get', pills: ['Every detail linked to the words it came from', 'The recording, by speaker'], tag: { kind: 'fast' as const, icon: 'check', text: 'A route, with reasons in plain words' } },
    ],
    guards: [
      { icon: 'shield', h: 'Recording consent comes first', p: 'Every call opens by asking. Where both people must agree to be recorded, nothing is kept until the caller says yes.', demo: '“This call is recorded so we get your claim right. Is that okay?”', hush: false },
      { icon: 'card', h: 'Card numbers are never taken', p: 'If a caller starts reading a card number, ClaimVoice stops them, and that moment is cut from the recording and the transcript.', demo: '“It\'s four-five', hush: true },
      { icon: 'person', h: 'A person can take over any call', p: 'Callers can ask for a person at any time. Supervisors can listen, pass ClaimVoice a note, or take the call. Nothing is ever denied automatically.', demo: '“Of course. I\'m bringing in Renée now.”', hush: false },
    ],
    comply: 'Designed to support the NAIC model bulletin on insurers\' use of AI, state call-recording consent rules, PCI DSS, GLBA, PIPEDA and Québec\'s Law 25. In English and French.',
    foot: 'Built for claims teams at regional insurers and agencies.',
    footLinks: ['Supervisors, sign in', 'Français', 'Privacy'],
    readLabel: 'The whole call, as text',
  },
  fr: {
    nav: ['Appeler la ligne de démo', 'Ce que votre équipe reçoit', 'Garanties'],
    signin: 'Superviseurs, connexion',
    eyebrow: 'Un appel de réclamation à Larkspur Mutual, Calgary · jeudi 8 janvier, 2 h 14, pendant une tempête de vent chinook',
    sample: 'Appel d\'exemple, voix synthétiques',
    h1a: 'Dites-moi ce qui s\'est passé.',
    h1b: 'Je m\'occupe du reste.',
    teaserWho: 'Dana, assurée',
    teaser: '« Le vent vient de briser notre puits de lumière. »',
    lede: 'ClaimVoice répond à votre ligne de réclamations à toute heure, en français ou en anglais. Il prend la première déclaration, pose les bonnes questions et remet à votre équipe un dossier où chaque détail renvoie aux mots d\'où il vient.',
    names: { cv: 'ClaimVoice', caller: 'Dana, assurée' },
    removed: 'retiré',
    horizon: { play: 'Écouter l\'appel', pause: 'Mettre en pause', playLabel: 'Écouter l\'appel', playSub: '', paused: 'Enregistrement en pause · numéro de carte', wave: 'Enregistrement de l\'appel. Cliquez pour vous déplacer. Moments :', moments: 'Moments de l\'appel' },
    slip: { label: 'Dossier', empty: 'Se remplit ici à mesure que chaque détail est entendu.', fromPolicy: 'selon la police' },
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
      { role: 'Équipe d\'accueil', line: '« Le vent a arraché le couvercle de mon compteur de gaz et ça sent le gaz. »', caller: true, gets: 'Vous recevez', pills: ['L\'appelant invité à sortir et à faire le 911', 'Un résumé, pour ne rien redemander'], tag: { kind: 'urgent' as const, icon: 'urgent', text: 'Sécurité urgente, attend une personne' } },
      { role: 'Expert en sinistres', line: '« Voici ce que j\'ai. C\'est bien ça? »', caller: false, gets: 'Vous recevez', pills: ['Chaque détail relié aux mots d\'où il vient', 'L\'enregistrement, par voix'], tag: { kind: 'fast' as const, icon: 'check', text: 'Un acheminement, avec des raisons claires' } },
    ],
    guards: [
      { icon: 'shield', h: 'Le consentement d\'abord', p: 'Chaque appel commence par la question. Là où les deux personnes doivent accepter, rien n\'est gardé avant le oui de l\'appelant.', demo: '« L\'appel est enregistré pour bien traiter votre réclamation. Ça vous convient? »', hush: false },
      { icon: 'card', h: 'Jamais de numéro de carte', p: 'Si un appelant commence à lire un numéro de carte, ClaimVoice l\'arrête, et ce moment est retiré de l\'enregistrement et de la transcription.', demo: '« C\'est quatre-cinq', hush: true },
      { icon: 'person', h: 'Une personne peut prendre l\'appel', p: 'L\'appelant peut demander une personne en tout temps. Les superviseurs peuvent écouter, glisser une note à ClaimVoice ou prendre l\'appel. Rien n\'est jamais refusé automatiquement.', demo: '« Bien sûr. Je fais venir Renée. »', hush: false },
    ],
    comply: 'Conçu pour soutenir le bulletin type de la NAIC sur l\'usage de l\'IA par les assureurs, les règles de consentement à l\'enregistrement, PCI DSS, GLBA, la LPRPDE et la Loi 25 du Québec. En français et en anglais.',
    foot: 'Conçu pour les équipes de réclamations des assureurs et cabinets régionaux.',
    footLinks: ['Superviseurs, connexion', 'English', 'Confidentialité'],
    readLabel: 'Tout l\'appel, en texte',
  },
}
const c = computed(() => COPY[lang.value])
useHead(() => ({ title: lang.value === 'fr' ? 'ClaimVoice · la ligne de réclamations qui écoute d\'abord' : 'ClaimVoice · the claims line that listens first', htmlAttrs: { lang: lang.value } }))

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
const slip = computed(() => slipAt(call.value.slip, t.value))
const showRoute = computed(() => t.value >= duration.value - 0.05)
const reading = ref(false)
const durationWords = computed(() => fmtDurationWords(duration.value, lang.value))
const horizonCopy = computed(() => ({ ...c.value.horizon, playSub: `${durationWords.value} · ${lang.value === 'fr' ? 'sous-titres activés' : 'captions on'}` }))
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
  if (el && (['INPUT', 'TEXTAREA', 'BUTTON', 'A', 'SELECT'].includes(el.tagName) || el.isContentEditable)) return
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

function ring(mode: 'voice' | 'typed' | 'other') {
  const otherLang = lang.value === 'fr' ? 'en' : 'fr'
  void navigateTo({ path: '/call', query: mode === 'typed' ? { type: '1', lang: lang.value } : mode === 'other' ? { lang: otherLang } : { lang: lang.value } })
}
</script>

<template>
  <div class="landing">
    <header class="lp-top">
      <CvLogo />
      <nav aria-label="Sections" class="lp-nav">
        <a href="#ring">{{ c.nav[0] }}</a><a href="#said">{{ c.nav[1] }}</a><a href="#guards">{{ c.nav[2] }}</a>
      </nav>
      <div class="right">
        <div class="seg lang" role="group" aria-label="Language / Langue">
          <button type="button" :aria-pressed="lang === 'en'" @click="prefs.lang.value = 'en'">
            English
          </button>
          <button type="button" :aria-pressed="lang === 'fr'" lang="fr" @click="prefs.lang.value = 'fr'">
            Français
          </button>
        </div>
        <NuxtLink class="signin" to="/sign-in">
          {{ c.signin }}
        </NuxtLink>
      </div>
    </header>

    <div class="eyebrow">
      <span class="dot" aria-hidden="true" /><span>{{ c.eyebrow }}</span><span class="sample tag plain">{{ c.sample }}</span>
    </div>

    <section class="stage" :aria-label="c.captions">
      <div class="intro" :class="{ gone: started || reading }">
        <h1>{{ c.h1a }}<br><em>{{ c.h1b }}</em></h1>
        <p class="teaser">
          <small>{{ c.teaserWho }}</small>{{ c.teaser }}
        </p>
        <p class="lede">
          {{ c.lede }}
        </p>
      </div>
      <LyricSheet v-if="started && !reading" :turns="call.turns" :t="t" :names="c.names" :removed="c.removed" />
      <div v-if="reading" class="readpanel">
        <ol :aria-label="c.readLabel">
          <li v-for="(x, i) in call.turns" :key="i" :class="{ cur: i === idx }">
            <button type="button" class="tm num" @click="player.seek(x.from)">
              {{ fmtClock(x.from) }}
            </button>
            <b>{{ x.who === 'cv' ? c.names.cv : 'Dana' }}</b>
            <span>{{ stripCardToken(x.text) }}<template v-if="x.hush != null"> <span class="hush">■■■■ {{ c.removed }}</span></template></span>
          </li>
        </ol>
      </div>
      <p class="sr-only-cv" aria-live="polite">
        <template v-if="lastFinal && playing">
          {{ lastFinal.who === 'cv' ? c.names.cv : c.names.caller }}: {{ lastFinal.text }}
        </template>
      </p>
    </section>

    <HorizonWave
      :bars="bars" :duration="duration" :t="t" :playing="playing" :turn-index="idx" :moments="call.moments"
      :hushing="hushing" :copy="horizonCopy" @toggle="player.toggle()" @seek="player.seek($event)"
    />

    <ClaimSlip :items="slip" :route="call.route" :show-route="showRoute" :animate="playing" :copy="c.slip" />

    <div class="controls">
      <time class="num clock">{{ fmtClock(t) }} / {{ fmtClock(duration) }}</time>
      <div class="seg" role="group" :aria-label="c.captions">
        <button type="button" :aria-pressed="!reading" @click="reading = false">
          <CvIcon name="captions" size="s" />{{ c.captions }}
        </button>
        <button type="button" :aria-pressed="reading" @click="reading = true">
          {{ c.read }}
        </button>
      </div>
      <div class="legend" aria-hidden="true">
        <span><i />{{ c.legendCv }}</span><span class="cl"><i />{{ c.legendCaller }}</span>
      </div>
      <div class="ring-cta">
        <small>{{ c.ringSmall[0] }}<br>{{ c.ringSmall[1] }}</small>
        <a class="btn soft" href="#ring"><CvIcon name="phone" />{{ c.ringH }}</a>
      </div>
    </div>

    <section id="ring" class="ringband" aria-labelledby="ring-h">
      <h2 id="ring-h">
        {{ c.ringH }}
      </h2>
      <p>{{ c.ringP }}</p>
      <div class="orbwrap">
        <DemoOrb state="idle" />
      </div>
      <p class="ringcap">
        {{ c.ringTry }}
      </p>
      <div class="ringactions">
        <button class="btn primary" type="button" @click="ring('voice')">
          <CvIcon name="mic" />{{ c.ringBtns[0] }}
        </button>
        <button class="btn soft on-sunk" type="button" @click="ring('typed')">
          <CvIcon name="keys" />{{ c.ringBtns[1] }}
        </button>
        <button class="btn soft on-sunk" type="button" :lang="lang === 'fr' ? 'en' : 'fr'" @click="ring('other')">
          <CvIcon name="lang" />{{ c.ringBtns[2] }}
        </button>
      </div>
      <p class="ringnote">
        {{ c.ringNote }}
      </p>
    </section>

    <section id="said" class="said">
      <h2>{{ c.saidH }}</h2>
      <div v-for="(r, i) in c.rows" :key="i" class="pair fade-scroll">
        <div class="role">
          {{ r.role }}
        </div>
        <div class="heardq" :class="{ caller: r.caller }">
          {{ r.line }}
        </div>
        <div class="gets">
          <p>{{ r.gets }}</p>
          <CvTag v-if="r.tag && r.tag.kind === 'urgent'" kind="urgent" :icon="r.tag.icon">
            {{ r.tag.text }}
          </CvTag>
          <span v-for="p in r.pills" :key="p" class="heard plain">{{ p }}</span>
          <CvTag v-if="r.tag && r.tag.kind === 'fast'" kind="fast" :icon="r.tag.icon">
            {{ r.tag.text }}
          </CvTag>
        </div>
      </div>
    </section>

    <section id="guards" class="guards" aria-label="Safeguards">
      <div v-for="g in c.guards" :key="g.h" class="guard">
        <div class="ic">
          <CvIcon :name="g.icon" size="l" />
        </div>
        <h3>{{ g.h }}</h3>
        <p>{{ g.p }}</p>
        <p class="demo">
          {{ g.demo }}<template v-if="g.hush">
            <span class="hush">■■■■ {{ c.removed }}</span>”
          </template>
        </p>
      </div>
    </section>
    <p class="comply">
      {{ c.comply }}
    </p>
    <footer class="foot">
      <CvLogo />
      <span>{{ c.foot }}</span>
      <div class="right">
        <NuxtLink to="/sign-in">
          {{ c.footLinks[0] }}
        </NuxtLink>
        <button type="button" class="linkbtn" @click="prefs.lang.value = lang === 'fr' ? 'en' : 'fr'">
          {{ c.footLinks[1] }}
        </button>
        <a href="#guards">{{ c.footLinks[2] }}</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.lp-top { display: flex; align-items: center; gap: 22px; height: 76px; padding: 0 40px; }
.lp-nav { display: flex; gap: 26px; margin-left: 36px; }
.lp-nav a { color: var(--cv-muted); text-decoration: none; font-weight: 600; font-size: 14.5px; }
.lp-nav a:hover { color: var(--cv-ink); }
.right { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.signin { font-weight: 650; font-size: 14.5px; color: var(--cv-ink); text-decoration: none; }
.lang button { height: 38px; padding: 0 14px; font-size: 14px; }

.eyebrow { padding: 0 40px; display: flex; align-items: center; gap: 10px; color: var(--cv-muted); font-size: 14px; font-weight: 550; min-height: 30px; }
.eyebrow .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cv-orchid); flex: none; }
.eyebrow .sample { margin-left: 6px; }

.stage { position: relative; height: 352px; margin: 4px 40px 0; overflow: hidden; }
.intro { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: flex-end; padding-bottom: 18px; transition: opacity 400ms var(--ease-voice), transform 400ms var(--ease-voice); }
.intro.gone { opacity: 0; transform: translateY(-24px); pointer-events: none; visibility: hidden; transition: opacity 400ms var(--ease-voice), transform 400ms var(--ease-voice), visibility 0s 400ms; }
.intro h1 { font-size: 82px; line-height: .98; font-weight: 750; letter-spacing: -0.045em; max-width: 900px; }
.intro h1 em { font-style: normal; color: var(--cv-orchid); }
.teaser { align-self: flex-end; text-align: right; margin: -96px 0 0; font-family: var(--font-display); font-size: 30px; font-weight: 600; color: var(--cv-caller); letter-spacing: -0.02em; max-width: 420px; line-height: 1.15; }
.teaser small { display: block; font-family: var(--font-sans); font-size: 13px; font-weight: 700; color: var(--cv-muted); letter-spacing: 0; margin-bottom: 4px; }
.lede { max-width: 560px; margin: 22px 0 0; color: var(--cv-muted); font-size: 17px; line-height: 1.55; }

.readpanel { position: absolute; inset: 0; overflow: auto; background: var(--cv-bg); padding: 4px 0; }
.readpanel ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.readpanel li { display: grid; grid-template-columns: 56px 110px 1fr; gap: 10px; font-size: calc(16px * var(--cv-caption-scale)); border-radius: 12px; padding: 2px 6px; }
.readpanel li.cur { background: var(--cv-orchid-wash); }
.readpanel .tm { border: 0; background: none; color: var(--cv-muted); text-align: left; padding: 0; font-weight: 600; }

.controls { display: flex; align-items: center; gap: 12px; margin: 10px 40px 0; min-height: 56px; }
.clock { font-weight: 650; font-size: 14px; color: var(--cv-muted); min-width: 92px; }
.legend { display: flex; gap: 14px; font-size: 12.5px; font-weight: 650; color: var(--cv-muted); margin-left: 10px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 4px; height: 14px; border-radius: 2px; background: var(--cv-orchid); display: inline-block; }
.legend .cl i { background: var(--cv-caller); }
.ring-cta { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.ring-cta small { color: var(--cv-muted); font-size: 13px; text-align: right; line-height: 1.35; }

.ringband { margin: 96px 0 0; padding: 88px 40px 96px; background: var(--cv-orchid-wash); display: grid; justify-items: center; text-align: center; }
.ringband h2 { font-size: 54px; font-weight: 750; letter-spacing: -0.04em; }
.ringband > p { color: var(--cv-muted); max-width: 560px; font-size: 17px; margin: 12px 0 0; }
.orbwrap { margin: 42px 0 28px; }
.ringcap { font-family: var(--font-display); font-size: 26px !important; font-weight: 600; color: var(--cv-caller) !important; max-width: 640px !important; line-height: 1.25; letter-spacing: -0.02em; }
.ringactions { display: flex; gap: 12px; margin-top: 28px; justify-content: center; flex-wrap: wrap; }
.ringnote { font-size: 13.5px !important; margin-top: 18px !important; }

.said { padding: 110px 40px 40px; max-width: 1240px; margin: 0 auto; }
.said h2 { font-size: 46px; font-weight: 750; letter-spacing: -0.04em; max-width: 760px; }
.pair { display: grid; grid-template-columns: 180px 1fr 1fr; gap: 28px; align-items: start; padding: 34px 0; }
.pair .role { font-weight: 750; font-size: 14px; color: var(--cv-muted); padding-top: 6px; }
.heardq { font-family: var(--font-display); font-size: 27px; font-weight: 600; line-height: 1.2; letter-spacing: -0.02em; }
.heardq.caller { color: var(--cv-caller); }
.gets { background: var(--cv-surface); border-radius: 20px; padding: 18px 20px; display: flex; flex-wrap: wrap; gap: 8px; }
.gets p { margin: 0 0 4px; width: 100%; font-size: 13px; font-weight: 750; color: var(--cv-muted); }
.fade-scroll { animation: rise-in linear both; animation-timeline: view(); animation-range: entry 0% entry 40%; }

.guards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; padding: 60px 40px; max-width: 1320px; margin: 0 auto; }
.guard { background: var(--cv-sunk); border-radius: 28px; padding: 28px; }
.guard .ic { width: 52px; height: 52px; border-radius: 50%; background: var(--cv-surface); display: grid; place-items: center; color: var(--cv-orchid-ink); margin-bottom: 18px; }
.guard h3 { font-size: 25px; font-weight: 700; letter-spacing: -0.025em; }
.guard p { color: var(--cv-muted); margin: 8px 0 0; }
.guard .demo { margin-top: 18px; font-family: var(--font-display); font-size: 18px; font-weight: 600; color: var(--cv-caller); }
.guard .demo .hush { margin-left: 6px; }
.comply { text-align: center; color: var(--cv-muted); font-size: 14.5px; padding: 10px 40px 40px; max-width: 900px; margin: 0 auto; }
.foot { display: flex; align-items: center; gap: 18px; padding: 28px 40px 40px; color: var(--cv-muted); font-size: 13.5px; }
.foot .right { gap: 18px; }
.linkbtn { border: 0; background: none; color: var(--cv-orchid-ink); text-decoration: underline; text-underline-offset: 3px; padding: 0; font-size: 13.5px; }

@media (max-width: 1100px) { .intro h1 { font-size: 64px; } .teaser { font-size: 24px; margin-top: -76px; } }
@media (max-width: 720px) {
  .lp-top { padding: 0 16px; height: 64px; }
  .lp-nav, .lp-top .lang { display: none; }
  .eyebrow { padding: 0 16px; font-size: 12.5px; flex-wrap: wrap; }
  .eyebrow .sample { display: none; }
  .stage { margin: 4px 16px 0; height: 476px; }
  .intro h1 { font-size: 48px; }
  .teaser { margin: 22px 0 0; font-size: 22px; }
  .lede { font-size: 15.5px; margin-top: 14px; }
  .readpanel li { grid-template-columns: 44px 1fr; }
  .readpanel li b { grid-column: 2; }
  .readpanel li > span { grid-column: 2; }
  .controls { margin: 10px 16px 0; flex-wrap: wrap; }
  .legend, .ring-cta small { display: none; }
  .ringband { padding: 64px 16px; }
  .ringband h2 { font-size: 36px; }
  .ringcap { font-size: 21px !important; }
  .said { padding: 72px 16px 24px; }
  .said h2 { font-size: 32px; }
  .pair { grid-template-columns: 1fr; gap: 12px; }
  .heardq { font-size: 22px; }
  .guards { grid-template-columns: 1fr; padding: 32px 16px; }
  .foot { flex-wrap: wrap; padding: 24px 16px; }
  .foot .right { margin-left: 0; flex-wrap: wrap; }
}
</style>
