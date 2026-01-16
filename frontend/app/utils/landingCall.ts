// The landing page's recorded call: Dana Whitcombe, Calgary, 2:14 a.m., the night of the Chinook windstorm. The
// voice line's audio and its timed transcript live in /audio/dana-call(.fr).{ogg,m4a,json}; until those load (or
// when they are missing) the page plays this built-in script on a silent clock with the same timings.
import type { Route } from '~/types/api'
import { phraseSpokenAt } from './transcript'

export interface CallTurn { who: 'cv' | 'caller', from: number, to: number, text: string, spans?: { text: string, key: string }[], hush?: number | null }
export interface CallMoment { key: string, label: string, at: number }
export interface SlipItem { key: string, label: string, at: number, hushed?: boolean, fromPolicy?: boolean, quote?: string | null }
export interface CallRouteReveal { route: Route, label: string, reasons: (string | { text: string, atSeconds?: number | null })[] }
export interface LandingCall {
  durationSeconds: number
  turns: CallTurn[]
  moments: CallMoment[]
  slip: SlipItem[]
  route: CallRouteReveal
  peaks?: { cv: number[], caller: number[] } | null
}

const EN: LandingCall = {
  durationSeconds: 76,
  turns: [
    { who: 'cv', from: 0, to: 5.4, text: 'Larkspur Mutual claims, this is ClaimVoice, an automated assistant. This call is recorded so we get your claim right. Is that okay?' },
    { who: 'caller', from: 5.8, to: 7.0, text: 'Yes, that\'s fine.', spans: [{ text: 'Yes, that\'s fine.', key: 'consent' }] },
    { who: 'cv', from: 7.3, to: 10.2, text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', from: 10.6, to: 14.6, text: 'It\'s L-M-A-B, two-oh-four, one-one-eight.', spans: [{ text: 'L-M-A-B, two-oh-four, one-one-eight.', key: 'policy' }] },
    { who: 'cv', from: 15.0, to: 17.4, text: 'Found it, Dana. Is everyone safe right now?' },
    { who: 'caller', from: 17.8, to: 23.6, text: 'Yes, we\'re fine. The wind just threw a piece of the neighbour\'s deck through our kitchen skylight.', spans: [{ text: 'we\'re fine.', key: 'hurt' }, { text: 'a piece of the neighbour\'s deck', key: 'debris' }, { text: 'through our kitchen skylight.', key: 'skylight' }] },
    { who: 'cv', from: 24.0, to: 27.2, text: 'I\'m sorry, that sounds frightening. Is the kitchen open to the weather?' },
    { who: 'caller', from: 27.6, to: 31.6, text: 'Not now. I\'ve taped a board and a garbage bag over the hole.', spans: [{ text: 'taped a board and a garbage bag over the hole.', key: 'skylight' }] },
    { who: 'cv', from: 32.0, to: 34.2, text: 'That\'s exactly right. When did it happen?' },
    { who: 'caller', from: 34.6, to: 37.6, text: 'About ten past two. Just a few minutes ago.', spans: [{ text: 'About ten past two.', key: 'when' }] },
    { who: 'cv', from: 38.0, to: 40.8, text: 'Is anything else damaged, inside or out?' },
    { who: 'caller', from: 41.2, to: 46.6, text: 'Some glass on the floor, that\'s all. Do you need my card for the deductible? It\'s four-five', spans: [{ text: 'Some glass on the floor,', key: 'glass' }], hush: 44.6 },
    { who: 'cv', from: 46.8, to: 52.0, text: 'Please stop there. I never take card numbers on this line, and that part of the recording is removed.', spans: [{ text: 'I never take card numbers', key: 'card' }] },
    { who: 'caller', from: 52.3, to: 53.4, text: 'Oh. Okay, good.' },
    { who: 'cv', from: 53.8, to: 58.2, text: 'I\'m texting you a link for photos of the skylight. Take them when it\'s light and safe.', spans: [{ text: 'texting you a link for photos', key: 'photos' }] },
    { who: 'caller', from: 58.6, to: 59.4, text: 'Got it.' },
    { who: 'cv', from: 59.8, to: 66.6, text: 'Here\'s what I have: wind damage at 1418 Elbow Drive Southwest around 2:10, the kitchen skylight broken and now covered, and nobody hurt. Is that right?' },
    { who: 'caller', from: 67.0, to: 67.9, text: 'That\'s right.' },
    { who: 'cv', from: 68.3, to: 75.6, text: 'Your claim number is CV-26-01842. Because of the storm, a repair crew will call you by 10 a.m. Call back any time.', spans: [{ text: 'CV-26-01842.', key: 'claimno' }] },
  ],
  moments: [
    { key: 'consent', label: 'Consent', at: 6.4 }, { key: 'policy', label: 'Policy', at: 13.8 }, { key: 'safe', label: 'Safe', at: 18.6 },
    { key: 'when', label: 'When', at: 35.8 }, { key: 'card', label: 'Card stopped', at: 44.6 }, { key: 'photos', label: 'Photos', at: 55 },
    { key: 'readback', label: 'Read-back', at: 59.8 }, { key: 'claimno', label: 'Claim no.', at: 68.3 },
  ],
  slip: [
    { key: 'consent', label: 'Recording consent', at: 6.4 },
    { key: 'policy', label: 'Policy LM-AB-204118 · Dana Whitcombe', at: 13.8 },
    { key: 'where', label: '1418 Elbow Dr SW', at: 15.2, fromPolicy: true },
    { key: 'hurt', label: 'Nobody hurt', at: 18.6 },
    { key: 'debris', label: 'Debris from the neighbour\'s deck', at: 21.4 },
    { key: 'skylight', label: 'Kitchen skylight smashed', at: 23.0 },
    { key: 'skylight', label: 'Kitchen skylight smashed, now covered', at: 30.8 },
    { key: 'when', label: 'Wind, about 2:10 a.m.', at: 35.8 },
    { key: 'card', label: 'Card number not taken', at: 47.0, hushed: true },
    { key: 'photos', label: 'Photo link sent', at: 55.0 },
    { key: 'claimno', label: 'Claim CV-26-01842', at: 70.0 },
  ],
  route: {
    route: 'fast_track',
    label: 'Fast-track',
    reasons: ['Wind warning confirmed for Calgary at 8 p.m.', 'Skylight covered, nothing open to the weather', 'Policy active 6 years, no open claims'],
  },
}

const FR: LandingCall = {
  ...EN,
  turns: [
    { who: 'cv', from: 0, to: 5.4, text: 'Réclamations Larkspur Mutual, ici ClaimVoice, un assistant automatisé. L\'appel est enregistré pour bien traiter votre réclamation. Ça vous convient?' },
    { who: 'caller', from: 5.8, to: 7.0, text: 'Oui, c\'est correct.', spans: [{ text: 'Oui, c\'est correct.', key: 'consent' }] },
    { who: 'cv', from: 7.3, to: 10.2, text: 'Merci. Quel est votre numéro de police, ou le numéro de téléphone au dossier?' },
    { who: 'caller', from: 10.6, to: 14.6, text: 'C\'est L-M-A-B, deux-zéro-quatre, un-un-huit.', spans: [{ text: 'L-M-A-B, deux-zéro-quatre, un-un-huit.', key: 'policy' }] },
    { who: 'cv', from: 15.0, to: 17.4, text: 'Je l\'ai, Dana. Est-ce que tout le monde est en sécurité?' },
    { who: 'caller', from: 17.8, to: 23.6, text: 'Oui, ça va. Le vent vient de lancer un morceau de la terrasse du voisin dans notre puits de lumière.', spans: [{ text: 'Oui, ça va.', key: 'hurt' }, { text: 'un morceau de la terrasse du voisin', key: 'debris' }, { text: 'dans notre puits de lumière.', key: 'skylight' }] },
    { who: 'cv', from: 24.0, to: 27.2, text: 'Je suis désolée, ça doit faire peur. La cuisine est-elle ouverte aux intempéries?' },
    { who: 'caller', from: 27.6, to: 31.6, text: 'Plus maintenant. J\'ai mis une planche et un sac sur le trou.', spans: [{ text: 'J\'ai mis une planche et un sac sur le trou.', key: 'skylight' }] },
    { who: 'cv', from: 32.0, to: 34.2, text: 'C\'est exactement ça. C\'est arrivé quand?' },
    { who: 'caller', from: 34.6, to: 37.6, text: 'Vers deux heures dix. Il y a quelques minutes.', spans: [{ text: 'Vers deux heures dix.', key: 'when' }] },
    { who: 'cv', from: 38.0, to: 40.8, text: 'Y a-t-il d\'autres dommages, dedans ou dehors?' },
    { who: 'caller', from: 41.2, to: 46.6, text: 'Du verre par terre, c\'est tout. Voulez-vous ma carte pour la franchise? C\'est quatre-cinq', spans: [{ text: 'Du verre par terre,', key: 'glass' }], hush: 44.6 },
    { who: 'cv', from: 46.8, to: 52.0, text: 'Arrêtez-vous là, s\'il vous plaît. Je ne prends jamais de numéro de carte sur cette ligne, et ce passage est retiré de l\'enregistrement.', spans: [{ text: 'Je ne prends jamais de numéro de carte', key: 'card' }] },
    { who: 'caller', from: 52.3, to: 53.4, text: 'Ah. D\'accord, tant mieux.' },
    { who: 'cv', from: 53.8, to: 58.2, text: 'Je vous envoie un lien par texto pour des photos du puits de lumière. Prenez-les quand il fera clair.', spans: [{ text: 'un lien par texto pour des photos', key: 'photos' }] },
    { who: 'caller', from: 58.6, to: 59.4, text: 'Parfait.' },
    { who: 'cv', from: 59.8, to: 66.6, text: 'Voici ce que j\'ai : dommages causés par le vent au 1418 Elbow Drive Sud-Ouest vers 2 h 10, le puits de lumière de la cuisine brisé puis couvert, et personne de blessé. C\'est bien ça?' },
    { who: 'caller', from: 67.0, to: 67.9, text: 'C\'est ça.' },
    { who: 'cv', from: 68.3, to: 75.6, text: 'Votre numéro de réclamation est CV-26-01842. À cause de la tempête, une équipe de réparation vous appellera avant 10 h. Rappelez quand vous voulez.', spans: [{ text: 'CV-26-01842.', key: 'claimno' }] },
  ],
  moments: [
    { key: 'consent', label: 'Consentement', at: 6.4 }, { key: 'policy', label: 'Police', at: 13.8 }, { key: 'safe', label: 'Sécurité', at: 18.6 },
    { key: 'when', label: 'Quand', at: 35.8 }, { key: 'card', label: 'Carte arrêtée', at: 44.6 }, { key: 'photos', label: 'Photos', at: 55 },
    { key: 'readback', label: 'Relecture', at: 59.8 }, { key: 'claimno', label: 'No de réclamation', at: 68.3 },
  ],
  slip: [
    { key: 'consent', label: 'Consentement à l\'enregistrement', at: 6.4 },
    { key: 'policy', label: 'Police LM-AB-204118 · Dana Whitcombe', at: 13.8 },
    { key: 'where', label: '1418 Elbow Dr SO', at: 15.2, fromPolicy: true },
    { key: 'hurt', label: 'Personne de blessé', at: 18.6 },
    { key: 'debris', label: 'Débris de la terrasse du voisin', at: 21.4 },
    { key: 'skylight', label: 'Puits de lumière brisé', at: 23.0 },
    { key: 'skylight', label: 'Puits de lumière brisé, couvert', at: 30.8 },
    { key: 'when', label: 'Vent, vers 2 h 10', at: 35.8 },
    { key: 'card', label: 'Numéro de carte non pris', at: 47.0, hushed: true },
    { key: 'photos', label: 'Lien pour photos envoyé', at: 55.0 },
    { key: 'claimno', label: 'Réclamation CV-26-01842', at: 70.2 },
  ],
  route: {
    route: 'fast_track',
    label: 'Traitement rapide',
    reasons: ['Avertissement de vent confirmé pour Calgary à 20 h', 'Puits de lumière couvert, rien d\'ouvert aux intempéries', 'Police en vigueur depuis 6 ans, aucune réclamation ouverte'],
  },
}

export function builtInCall(lang: 'en' | 'fr'): LandingCall {
  return lang === 'fr' ? FR : EN
}

/** Validate the shape of a timed-transcript JSON file; anything unusable returns null (the page keeps the script). */
export function parseLandingCall(raw: unknown): LandingCall | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Partial<LandingCall>
  if (typeof r.durationSeconds !== 'number' || !Array.isArray(r.turns) || !r.turns.length) return null
  const okTurn = (t: CallTurn) => (t.who === 'cv' || t.who === 'caller') && typeof t.from === 'number' && typeof t.to === 'number' && typeof t.text === 'string'
  if (!r.turns.every(okTurn)) return null
  const base = EN
  const slip = (Array.isArray(r.slip) && r.slip.length ? r.slip : base.slip).map(normaliseSlip)
  return {
    durationSeconds: r.durationSeconds,
    turns: r.turns,
    moments: Array.isArray(r.moments) && r.moments.length ? r.moments : base.moments,
    slip: alignSlip(r.turns, slip),
    route: r.route && typeof r.route === 'object' && 'route' in r.route ? r.route : base.route,
    peaks: r.peaks && Array.isArray(r.peaks.cv) && Array.isArray(r.peaks.caller) ? r.peaks : null,
  }
}

/** "1418 Elbow Drive SW, from the policy" → label "1418 Elbow Drive SW" with the from-the-policy chip. */
export function normaliseSlip(item: SlipItem): SlipItem {
  const m = item.label.match(/^(.*?)[,·]\s*(from the policy|selon la police)$/i)
  return m ? { ...item, label: m[1]!.trim(), fromPolicy: true } : item
}

/**
 * Land each slip value when its words have been said: if the turn under `at` has a heard span with the same key,
 * move `at` to the moment that span's last word is spoken (so Pluck flies from words that are already washed).
 */
export function alignSlip(turns: CallTurn[], slip: SlipItem[]): SlipItem[] {
  return slip.map((item) => {
    if (item.fromPolicy) return item
    const turn = turns.find(t => item.at >= t.from - 0.05 && item.at < t.to && t.spans?.some(s => s.key === item.key))
    const span = turn?.spans?.find(s => s.key === item.key)
    if (!turn || !span) return item
    const spoken = phraseSpokenAt(turn, span.text)
    return spoken != null && spoken > item.at ? { ...item, at: Math.round(spoken * 100) / 100 } : item
  })
}

export function reasonText(r: CallRouteReveal['reasons'][number]): string {
  return typeof r === 'string' ? r : r.text
}

/** The latest value of each slip key at time t, in first-heard order. */
export function slipAt(slip: SlipItem[], t: number): SlipItem[] {
  const latest = new Map<string, SlipItem>()
  const order: string[] = []
  for (const f of slip) {
    if (f.at > t) continue
    if (!latest.has(f.key)) order.push(f.key)
    latest.set(f.key, f)
  }
  return order.map(k => latest.get(k)!)
}

/**
 * Every value the notice shows, in time order: the call's slip plus the read-back, which is filled when the caller
 * confirms ClaimVoice's summary (the first caller turn after the read-back moment), unless the slip already has it.
 */
export function noticeItems(call: LandingCall, readBackLabel: string): SlipItem[] {
  const items = [...call.slip]
  const moment = call.moments.find(m => m.key === 'readback')
  if (moment && !items.some(i => i.key === 'readback')) {
    const confirm = call.turns.find(t => t.who === 'caller' && t.from >= moment.at)
    if (confirm) items.push({ key: 'readback', label: readBackLabel, at: confirm.to, quote: confirm.text.replace(/[.,]$/, '') })
  }
  return items.sort((a, b) => a.at - b.at)
}
