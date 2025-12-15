// Call quality: every finished call is scored on the 11-item rubric (docs/API_CONTRACT.md §1.9); nine are in the review
// queue. Also builds the two queued calls that have no claim (a card number read aloud, an unverified caller).
import type { Band, Bead, CallDetail, CallEvent, QaItem, QaQueueItem, QaScore, Recording, Transcript, Turn } from '~/types/api'
import { callDetail, flag } from './calls'
import { GREETING_EN } from './claimkit'
import { CARD, type Clock, moment, P, recordingFrom, ref, stage, Talk, TZ, timelineFrom, uid, type Who } from './kit'

type Key =
  | 'consent_first' | 'consent_rule' | 'identity_verified' | 'required_fields' | 'safety_check' | 'read_back'
  | 'empathy' | 'no_card_numbers' | 'handoff_correct' | 'language_honoured' | 'no_promises'

const RUBRIC: { key: Key, label: string, points: number, critical: boolean, method: QaItem['method'] }[] = [
  { key: 'consent_first', label: 'Consent first', points: 10, critical: true, method: 'rule' },
  { key: 'consent_rule', label: 'Right consent rule for the region', points: 4, critical: true, method: 'rule' },
  { key: 'identity_verified', label: 'Identity checked', points: 8, critical: false, method: 'rule' },
  { key: 'required_fields', label: 'Required details', points: 16, critical: false, method: 'rule' },
  { key: 'safety_check', label: 'Safety asked', points: 10, critical: true, method: 'rule' },
  { key: 'read_back', label: 'Read-back', points: 12, critical: false, method: 'rule' },
  { key: 'empathy', label: 'Kind words', points: 8, critical: false, method: 'language_check' },
  { key: 'no_card_numbers', label: 'No card numbers', points: 10, critical: true, method: 'rule' },
  { key: 'handoff_correct', label: 'Right hand-off', points: 16, critical: false, method: 'rule' },
  { key: 'language_honoured', label: 'Caller\'s language kept', points: 3, critical: false, method: 'language_check' },
  { key: 'no_promises', label: 'No promises about payment', points: 3, critical: false, method: 'language_check' },
]
const BEADS: Key[] = ['consent_first', 'identity_verified', 'required_fields', 'empathy', 'no_card_numbers', 'handoff_correct']
const BAND_LABEL: Record<Band, string> = { good: 'Good', needs_attention: 'Needs attention', failed: 'Failed' }

interface ItemOverride {
  passed?: boolean | null
  note?: string
  evidence?: [turn: string, phrase: string][]
  at?: number
}

export interface QaSpec {
  talk: Talk
  call: CallDetail
  claimId: string | null
  claimNumber: string | null
  details: [have: number, of: number]
  items?: Partial<Record<Key, ItemOverride>>
  status: QaScore['status']
  queued?: string
  review?: { by: Who, at: string, note: string }
  focus?: { atSeconds: number, text: string }
}

/** The sentence of a turn that contains a phrase (always a substring of the stored text). */
function sentenceWith(text: string, needle: string): string {
  const i = text.indexOf(needle)
  if (i < 0) return needle
  let start = 0
  for (const mark of ['. ', '? ', '! ', ': ']) {
    const j = text.lastIndexOf(mark, i)
    if (j >= 0 && j + 2 > start && j + 2 <= i) start = j + 2
  }
  let end = text.length
  for (const mark of ['.', '?', '!']) {
    const j = text.indexOf(mark, i + needle.length)
    if (j >= 0 && j + 1 < end) end = j + 1
  }
  return text.slice(start, end)
}

function find(talk: Talk, speakers: Turn['speaker'][], needles: string[]): { turn: Turn, needle: string } | null {
  for (const t of talk.turns) {
    if (!speakers.includes(t.speaker)) continue
    const needle = needles.find(n => t.text.includes(n))
    if (needle) return { turn: t, needle }
  }
  return null
}

const NEEDLES: Partial<Record<Key, [Turn['speaker'][], string[]]>> = {
  consent_first: [['line'], ['This call is recorded', 'this call is recorded', 'L\'appel est enregistré']],
  consent_rule: [['line'], ['This call is recorded', 'this call is recorded', 'L\'appel est enregistré']],
  identity_verified: [['line', 'person'], ['Found it', 'Found you', 'I\'ve found a policy', 'Je vous ai trouvé']],
  required_fields: [['line', 'person'], ['Here\'s what I have', 'Voici ce que j\'ai']],
  safety_check: [['line'], ['is everyone safe', 'are you safe', 'est-ce que tout le monde est en sécurité']],
  read_back: [['line', 'person'], ['Here\'s what I have', 'Voici ce que j\'ai']],
  empathy: [['line', 'person'], ['I\'m sorry', 'désolée', 'I\'m glad', 'That sounds', 'That was decent', 'Goodness', 'Ice is no fun', 'No need to be sorry']],
  no_card_numbers: [['caller'], [CARD]],
  handoff_correct: [['line', 'person'], ['bringing in a person', 'it\'s Jamal']],
  no_promises: [['line', 'person'], ['adjuster', 'expert', 'Fast-track', 'fast track']],
}

function defaultNote(key: Key, s: QaSpec, hasCard: boolean, hasHandoff: boolean): string {
  switch (key) {
    case 'consent_first': return 'The recording notice came before any questions.'
    case 'consent_rule': return `${s.call.consent.ruleLabel} followed.`
    case 'identity_verified': return 'Policy found and the caller matched it.'
    case 'required_fields': return `${s.details[0]} of ${s.details[1]} required details collected.`
    case 'safety_check': return 'Safety asked as soon as the policy was found.'
    case 'read_back': return 'Read the details back and the caller confirmed them.'
    case 'empathy': return 'Acknowledged how the caller was feeling.'
    case 'no_card_numbers': return hasCard ? 'The caller started a card number; ClaimVoice stopped them and the moment was removed.' : 'No card numbers on the call.'
    case 'handoff_correct': return hasHandoff ? 'Brought in a person when the caller needed one.' : 'No hand-off was needed.'
    case 'language_honoured': return s.talk.language === 'fr' ? 'Kept in French throughout, as the caller chose.' : 'Kept in English throughout.'
    case 'no_promises': return 'Made no promises about payment or timing of a decision.'
  }
}

export function scoreCall(c: Clock, s: QaSpec): QaScore {
  const hasCard = s.talk.turns.some(t => t.redactions > 0)
  const hasHandoff = s.talk.turns.some(t => t.stage === 'handoff')
  const items: QaItem[] = RUBRIC.map((r) => {
    const o: ItemOverride = s.items?.[r.key] ?? {}
    const naturalPassed = r.key === 'handoff_correct' && !hasHandoff ? null : true
    const passed = o.passed !== undefined ? o.passed : naturalPassed
    // Required details earn partial points above 7 in 10 collected; every other missed item earns none.
    const share = s.details[1] ? s.details[0] / s.details[1] : 0
    const points = passed === true
      ? r.points
      : passed === false && r.key === 'required_fields' ? Math.round(r.points * Math.max(0, (share - 0.7) / 0.3)) : 0
    let evidence: { turnId: string, quote: string }[]
    let atSeconds: number | null = o.at ?? null
    if (o.evidence) {
      evidence = o.evidence.map(([turn, phrase]) => ({ turnId: s.talk.t(turn).id, quote: sentenceWith(s.talk.t(turn).text, s.talk.quote(turn, phrase).quote) }))
      const first = o.evidence[0]
      if (atSeconds == null && first) atSeconds = s.talk.sec(first[0])
    } else if (r.key === 'language_honoured') {
      const t = s.talk.turns.find(x => x.speaker === 'caller')
      evidence = t ? [{ turnId: t.id, quote: sentenceWith(t.text, t.text.slice(0, 8)) }] : []
      if (atSeconds == null && t) atSeconds = Math.floor(t.atMs / 1000)
    } else {
      const spec = NEEDLES[r.key]
      const hit = spec ? find(s.talk, spec[0], spec[1]) : null
      evidence = hit ? [{ turnId: hit.turn.id, quote: sentenceWith(hit.turn.text, hit.needle) }] : []
      if (atSeconds == null && hit) atSeconds = Math.floor(hit.turn.atMs / 1000)
    }
    return {
      key: r.key,
      label: r.label,
      passed,
      points,
      maxPoints: r.points,
      critical: r.critical,
      method: r.method,
      note: o.note ?? defaultNote(r.key, s, hasCard, hasHandoff),
      evidence,
      atSeconds,
      reviewerVerdict: s.review ? 'agree' : null,
      reviewerNote: null,
    }
  })
  const applicable = items.filter(i => i.passed !== null)
  const max = applicable.reduce((a, i) => a + i.maxPoints, 0)
  const earned = applicable.reduce((a, i) => a + i.points, 0)
  const score = max ? Math.round((100 * earned) / max) : 0
  const criticalFailed = items.some(i => i.critical && i.passed === false)
  const band: Band = criticalFailed || score < 70 ? 'failed' : score >= 85 ? 'good' : 'needs_attention'
  const beads: Bead[] = BEADS.map((k) => {
    const i = items.find(x => x.key === k)
    return {
      key: k,
      label: i?.label ?? k,
      passed: i?.passed ?? null,
      detail: k === 'required_fields' && i?.passed != null ? `${s.details[0]}/${s.details[1]}` : null,
    }
  })
  const endedAt = s.call.endedAt ?? s.call.startedAt
  return {
    callId: s.call.id,
    claimId: s.claimId,
    claimNumber: s.claimNumber,
    score,
    band,
    bandLabel: BAND_LABEL[band],
    status: s.status,
    items,
    beads,
    focus: s.focus ?? null,
    scoredAt: c.plus(endedAt, 60),
    scorerVersion: 'Rubric 3',
    reviewedBy: s.review ? ref(s.review.by) : null,
    reviewedAt: s.review?.at ?? null,
    reviewNote: s.review?.note ?? null,
  }
}

export function queueItem(s: QaSpec, q: QaScore): QaQueueItem {
  return {
    callId: s.call.id,
    claimId: s.claimId,
    reference: s.call.reference,
    claimNumber: s.claimNumber,
    startedAt: s.call.startedAt,
    durationSeconds: s.call.durationSeconds ?? 0,
    language: s.call.language,
    lossTypeLabel: s.call.lossTypeLabel,
    score: q.score,
    band: q.band,
    bandLabel: q.bandLabel,
    failedItems: q.items.filter(i => i.passed === false).map(i => i.label),
    beads: q.beads,
    callerLabel: s.call.callerLabel,
    lineLabel: s.call.lineLabel ?? null,
    reviewer: q.reviewedBy,
    status: q.status,
    reasonQueued: s.queued ?? 'Random sample',
  }
}

// ---------------------------------------------------------------- calls without a claim

export interface LooseCall {
  call: CallDetail
  talk: Talk
  transcript: Transcript
  recording: Recording
  timeline: CallEvent[]
}

/** Rosa Delgado, Denver: called to pay a deductible by card and read most of the number before she was stopped. */
export function buildRosa(c: Clock): LooseCall {
  const n = 51
  const talk = new Talk(uid('call', n), n, 'en', 'Rosa Delgado', [
    { who: 'line', at: 0, end: 7, stage: 'consent', text: GREETING_EN },
    { who: 'caller', at: 7.6, end: 9, stage: 'consent', ref: 'consent', text: 'Sure, that\'s fine.' },
    { who: 'line', at: 9.5, end: 14, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', at: 15, end: 22, stage: 'identity', ref: 'policy', text: 'It\'s LM-CO-519027. I\'m calling about the claim for my windshield.' },
    { who: 'line', at: 23, end: 27, stage: 'safety', ref: 'safety', text: 'Found it, Rosa. Before anything else: is everyone safe right now?' },
    { who: 'caller', at: 28, end: 34, stage: 'loss_type', ref: 'story', text: 'Oh yes, everyone\'s fine. I just want to pay my deductible so the glass shop can start.' },
    { who: 'line', at: 35, end: 43, stage: 'coverage', ref: 'explain', text: 'The glass shop collects the deductible when they do the work, so there\'s nothing to pay us today.' },
    { who: 'caller', at: 44, end: 66, stage: 'coverage', ref: 'card', text: `Oh, okay. Well, can I just give you my card anyway, so it's done? It's ${CARD}` },
    { who: 'line', at: 66.6, end: 76, stage: 'coverage', ref: 'stop', text: 'Please stop there. I never take card numbers on this line, and that part of the recording is removed. The glass shop will take it when they replace the windshield.' },
    { who: 'caller', at: 77, end: 79, stage: 'coverage', text: 'Got it, sorry.' },
    { who: 'line', at: 79.5, end: 85, stage: 'wrap_up', ref: 'close', text: 'No need to be sorry. Is there anything else I can help with today?' },
    { who: 'caller', at: 85.5, end: 88, stage: 'wrap_up', text: 'No, that\'s it. Thanks.' },
    { who: 'line', at: 88.5, end: 92, stage: 'wrap_up', text: 'Thanks for calling Larkspur Mutual. Take care.' },
  ])
  const endedAt = c.atIso(-2, '13:12:33', TZ.denver)
  const startedAt = c.plus(endedAt, -93)
  const call = callDetail(c, {
    n, startedAt, endedAt, state: 'ended', language: 'en', callerLabel: 'Rosa Delgado', region: 'US-CO', place: 'Englewood',
    lossType: null, outcome: 'no_claim', stage: stage('ended'), consentTurn: talk.t('consent'), policyNo: 151,
    policyNumber: 'LM-CO-519027', summary: 'Asked to pay a windshield deductible by card. Told the glass shop collects it; card number removed.',
    flags: [flag('card_number_removed', 'Card number read aloud', 'Read for 9 seconds before ClaimVoice stopped her. Removed.', 'warning', c.plus(startedAt, 57), talk.t('card'))],
  })
  const recording = recordingFrom(talk, {
    seed: 5151,
    hushes: [[57, 66]],
    duration: 93,
    retainedUntil: `${Number(c.date(-2, TZ.denver).slice(0, 4)) + 7}${c.date(-2, TZ.denver).slice(4)}`,
    moments: [moment('consent', 'Consent', talk, 'consent'), moment('policy', 'Policy', talk, 'safety'), moment('safety', 'Card number stopped', talk, 'card', 57)],
  })
  const timeline = timelineFrom(talk, startedAt, c, [
    { atMs: 9000, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
    { atMs: 22400, kind: 'tool', label: 'Policy found in 0.2 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } },
    { atMs: 93000, kind: 'ended', label: 'Call ended · no claim needed', actor: 'ClaimVoice', data: {} },
  ])
  return { call, talk, transcript: { callId: call.id, language: 'en', retained: true, notice: null, turns: talk.turns }, recording, timeline }
}

/** An unverified caller in Calgary asking about her mother's policy; handed to Jamal after identity could not be checked. */
export function buildUnverified(c: Clock): LooseCall {
  const n = 52
  const talk = new Talk(uid('call', n), n, 'en', 'Unverified caller', [
    { who: 'line', at: 0, end: 7, stage: 'consent', text: GREETING_EN },
    { who: 'caller', at: 7.5, end: 8.5, stage: 'consent', ref: 'consent', text: 'Yes.' },
    { who: 'line', at: 9, end: 13.5, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', at: 14, end: 21, stage: 'identity', ref: 'mom', text: 'I don\'t have it with me. It\'s my mom\'s policy, she\'s in the hospital.' },
    { who: 'line', at: 21.5, end: 28, stage: 'identity', ref: 'postal', text: 'I\'m sorry to hear that. Can you tell me the postal code on the policy, so I can find it?' },
    { who: 'caller', at: 29, end: 34, stage: 'identity', text: 'I think it starts with T2E. I\'m not sure of the rest.' },
    { who: 'line', at: 35, end: 40, stage: 'identity', text: 'That\'s all right. Could you tell me her date of birth instead?' },
    { who: 'caller', at: 41, end: 46, stage: 'identity', ref: 'ask', text: 'I\'d have to look. Can I just talk to someone?' },
    { who: 'line', at: 46.5, end: 52, stage: 'handoff', ref: 'bring', text: 'Of course. I\'m bringing in a person who can help find the policy.' },
    { who: 'person', at: 70, end: 76, stage: 'handoff', ref: 'jamal', label: P.jamal.name, text: 'Hi, it\'s Jamal at Larkspur. Let\'s find your mom\'s policy together.' },
  ])
  const endedAt = c.atIso(-2, '10:11:40')
  const startedAt = c.plus(endedAt, -77)
  const call = callDetail(c, {
    n, startedAt, endedAt, state: 'ended', language: 'en', callerLabel: 'Unverified caller', region: 'CA-AB', place: 'Calgary',
    lossType: null, outcome: 'handed_off', stage: stage('ended'), consentTurn: talk.t('consent'), policyNo: null, policyNumber: null,
    summary: 'Calling about her mother\'s policy; could not confirm identity. Handed to Jamal Haddad.',
    handoff: {
      id: uid('handoff', n),
      callId: uid('call', n),
      reason: 'identity_unverified',
      reasonLabel: 'Identity not confirmed',
      detail: 'Calling for her mother; did not have the policy number, postal code or date of birth.',
      priority: 'high',
      state: 'completed',
      requestedAt: c.plus(startedAt, 47),
      waitingSeconds: 23,
      acceptedBy: ref(P.jamal),
      acceptedAt: c.plus(startedAt, 70),
      callerLabel: 'Unverified caller',
      lineLabel: 'Line 1',
      place: 'Calgary',
      lossTypeLabel: null,
      language: 'en',
      summary: 'Calling about her mother\'s policy while her mother is in hospital.\nCould not give the policy number, postal code or date of birth.',
      actionsTaken: ['Asked for the policy number, postal code and date of birth', 'Brought in a person when she asked'],
      to: ref(P.jamal),
      team: 'intake',
    },
    lineLabel: 'Line 1',
  })
  const recording = recordingFrom(talk, {
    seed: 5252,
    duration: 77,
    retainedUntil: `${Number(c.date(-2).slice(0, 4)) + 7}${c.date(-2).slice(4)}`,
    moments: [moment('consent', 'Consent', talk, 'consent'), moment('handoff', 'Asked for a person', talk, 'ask'), moment('handoff', 'Jamal joined', talk, 'jamal')],
  })
  const timeline = timelineFrom(talk, startedAt, c, [
    { atMs: 8500, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
    { atMs: 47000, kind: 'handoff', label: 'Identity not confirmed: waiting for a person', actor: 'ClaimVoice', data: { reason: 'identity_unverified' } },
    { atMs: 70000, kind: 'handoff', label: 'Jamal Haddad took the call', actor: P.jamal.name, data: { state: 'accepted' } },
    { atMs: 77000, kind: 'ended', label: 'ClaimVoice left the call; Jamal carried on', actor: 'ClaimVoice', data: {} },
  ])
  return { call, talk, transcript: { callId: call.id, language: 'en', retained: true, notice: null, turns: talk.turns }, recording, timeline }
}
