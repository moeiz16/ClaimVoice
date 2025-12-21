// A local stand-in for the voice line, used only with the API mock: the same data-channel protocol (Part 4.3) driven
// by a short scripted dialogue, so the demo-line page can be worked on without the server.
import type { ClientMessage, Lang, ServerMessage, Slot, StageInfo } from '~/types/api'
import type { CallTransport, TransportEvents } from '~/utils/voiceTransport'

const STEPS = ['Consent', 'Policy', 'Safety', 'What happened', 'Photos', 'Coverage', 'Read-back']
const stage = (step: number, key: string): StageInfo => ({ key, label: STEPS[step - 1]!, step, stepLabel: STEPS[step - 1]!, steps: 7, nextLabel: STEPS[step] ? `${STEPS[step]} next` : null })

const LINES: Record<Lang, string[]> = {
  en: [
    'Larkspur Mutual claims, this is ClaimVoice, an automated assistant. This call is recorded so we get your claim right. Is that okay?',
    'Thank you. What\'s your policy number, or the phone number on your policy?',
    'Found it. Before anything else: is everyone safe right now?',
    'Good. Tell me what happened, in your own words.',
    'Thank you. I\'m texting you a link for photos. Take them when it\'s light and safe.',
    'Here\'s what I have: {what}. Is that right?',
    'Your claim number is CV-26-01870. An adjuster will call you by 10 a.m. Call back any time.',
  ],
  fr: [
    'Réclamations Larkspur Mutual, ici ClaimVoice, un assistant automatisé. L\'appel est enregistré pour bien traiter votre réclamation. Ça vous convient?',
    'Merci. Quel est votre numéro de police, ou le numéro de téléphone au dossier?',
    'Je l\'ai. Avant tout : est-ce que tout le monde est en sécurité?',
    'Bien. Racontez-moi ce qui s\'est passé, dans vos mots.',
    'Merci. Je vous envoie un lien par texto pour des photos. Prenez-les quand il fera clair.',
    'Voici ce que j\'ai : {what}. C\'est bien ça?',
    'Votre numéro de réclamation est CV-26-01870. Un expert vous appellera avant 10 h. Rappelez quand vous voulez.',
  ],
}

export function looksLikeCardNumber(text: string): boolean {
  const digits = text.replace(/\D/g, '')
  const spoken = (text.toLowerCase().match(/\b(zero|one|two|three|four|five|six|seven|eight|nine|oh|zéro|un|deux|trois|quatre|cinq|sept|huit|neuf)\b/g) ?? []).length
  return /\b(card|carte|visa|mastercard)\b/i.test(text) && (digits.length >= 4 || spoken >= 4)
}

export function connectLocal(language: Lang, ev: TransportEvents): CallTransport {
  let step = 0
  let seq = 0
  let what = ''
  let closed = false
  const lang = language
  const emit = (m: ServerMessage, delay = 400) => setTimeout(() => { if (!closed) ev.onMessage(m) }, delay)
  const say = (text: string, delay = 600) => {
    const turnId = `local-${++seq}`
    emit({ type: 'line.say', turnId, text, language: lang, voiceLang: lang === 'fr' ? 'fr-CA' : 'en-CA', interruptible: true, expectsAnswer: true }, delay)
  }
  const slot = (key: string, label: string, display: string): ServerMessage => ({
    type: 'claim_file.slot', progress: Math.min(1, step / 6),
    slot: { key, label, value: display, display, confidence: 0.9, confidenceLabel: 'sure', source: 'heard', sourceLabel: '', span: null, heardAtSeconds: null, changedAtSeconds: null, confirmed: false, required: true, history: [] } satisfies Slot,
  })
  const advance = (text: string) => {
    if (looksLikeCardNumber(text)) {
      emit({ type: 'call.notice', kind: 'recording_paused', text: lang === 'fr' ? 'Enregistrement en pause pendant qu\'on saute ce numéro' : 'Recording paused while we skip that number' }, 100)
      emit({ type: 'call.flag', flag: { kind: 'card_number_removed', label: 'Card number removed', detail: '', severity: 'info', at: new Date().toISOString() } }, 150)
      say(lang === 'fr' ? 'Arrêtez-vous là, s\'il vous plaît. Je ne prends jamais de numéro de carte sur cette ligne.' : 'Please stop there. I never take card numbers on this line, and that part of the recording is removed.')
      return
    }
    step++
    if (step === 1) emit(slot('consent', 'Consent', lang === 'fr' ? 'Consentement donné' : 'Recording consent given'), 200)
    if (step === 2) emit(slot('policy', 'Policy', lang === 'fr' ? 'Police trouvée' : 'Policy found'), 200)
    if (step === 3) emit(slot('hurt', 'Safety', /no|non|hurt|bless/i.test(text) && !/fine|ok|bien|ça va/i.test(text) ? text.slice(0, 40) : (lang === 'fr' ? 'Personne de blessé' : 'Nobody hurt')), 200)
    if (step === 4) { what = text.replace(/[.!?]+$/, '').slice(0, 90); emit(slot('what', 'What happened', what), 200) }
    if (step === 5) emit(slot('photos', 'Photos', lang === 'fr' ? 'Lien envoyé par texto' : 'Photo link texted'), 200)
    const keys = ['greeting', 'identity', 'safety', 'loss_details', 'photos', 'read_back', 'wrap_up']
    emit({ type: 'call.stage', stage: stage(Math.min(7, [1, 2, 3, 4, 5, 7, 7][step] ?? 7), keys[Math.min(step, 6)]!) }, 250)
    if (step < 6) say(LINES[lang][step]!.replace('{what}', what || (lang === 'fr' ? 'ce que vous m\'avez dit' : 'what you told me')))
    else {
      say(LINES[lang][6]!)
      emit({
        type: 'call.ended', reason: 'completed', claimNumber: 'CV-26-01870', summary: what || null,
        nextSteps: lang === 'fr' ? ['Un expert vous appelle avant 10 h', 'Envoyez vos photos par le lien'] : ['An adjuster calls you by 10 a.m.', 'Send your photos with the link'],
        route: { route: 'adjuster', label: lang === 'fr' ? 'Expert en sinistres' : 'Adjuster', reasons: [{ text: lang === 'fr' ? 'Les dommages demandent une visite' : 'Damage needs a visit to price' }, { text: lang === 'fr' ? 'Personne de blessé' : 'Nobody hurt' }, { text: lang === 'fr' ? 'Police active, aucune réclamation ouverte' : 'Policy active, no open claims' }] },
      }, 6500)
    }
  }
  setTimeout(() => {
    ev.onOpen()
    emit({ type: 'call.ready', callId: 'local', mode: 'browser_speech', language: lang, stage: stage(1, 'greeting') }, 100)
    say(LINES[lang][0]!, 700)
  }, 300)
  return {
    kind: 'local',
    send(msg: ClientMessage) {
      if (msg.type === 'caller.text' && msg.final && msg.text.trim()) {
        emit({ type: 'transcript.turn', turn: { id: `c-${++seq}`, seq, speaker: 'caller', speakerLabel: 'You', text: msg.text, language: lang, atMs: 0, endMs: 0, stage: '', confidence: msg.confidence ?? null, interrupted: false, redactions: 0, flags: [] } }, 50)
        advance(msg.text)
      }
      if (msg.type === 'caller.hangup') { closed = true; ev.onClose('hangup') }
    },
    close() { closed = true; ev.onClose('hangup') },
  }
}
