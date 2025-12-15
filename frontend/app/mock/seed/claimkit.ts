// Builds one finished claim and everything around it (its call, transcript, recording, photos, routing, referral,
// timeline and texts) from a compact spec. Light claims use a short scripted call template; rich claims pass their own.
import type {
  CallDetail, CallEvent, Claim, ClaimFileSection, ClaimStatus, Flag, Iso, IsoDate, Lang, Moment, Photo, Reason,
  Recording, Route, RoutingDecision, ScoreBand, SiuIndicator, SiuReferral, SmsMessage, Transcript,
} from '~/types/api'
import { callDetail, flag, tzFor } from './calls'
import {
  type Clock, claimFile, editedBy, fmt, fromPolicy, heard, type Line, lookedUp, moment, notYet, ref, recordingFrom, type Scene,
  sceneUrl, section, slot, type SlotOpts, stage, Talk, timelineFrom, uid, type Who,
} from './kit'
import { LOSS_LABEL, type LossKey, REGION_LABEL, type RegionCode } from './settings'

export const STATUS_LABEL: Record<ClaimStatus, string> = {
  new: 'New',
  assigned: 'Assigned',
  in_review: 'In review',
  waiting_on_customer: 'Waiting on the customer',
  closed: 'Closed',
}
export const ROUTE_LABEL: Record<Route, string> = { fast_track: 'Fast-track', adjuster: 'Adjuster', special_investigation: 'Closer look' }
export const ROUTING_STATEMENT = 'For a person to review. A sign is never a reason to deny a claim on its own, and nothing here was decided automatically.'
export const SIU_STATEMENT = 'A referral is a request for review. It is not a finding of fraud and never denies a claim.'
export const GREETING_EN = 'Larkspur Mutual claims, this is ClaimVoice, an automated assistant. This call is recorded so we get your claim right. Is that okay?'
export const GREETING_FR = 'Bonjour, ici ClaimVoice, l\'assistant automatisé des réclamations de Larkspur Mutual. L\'appel est enregistré pour bien traiter votre réclamation. Est-ce que ça vous convient?'
const GREETING_FR_EN = 'Hello, this is ClaimVoice, Larkspur Mutual\'s automated claims assistant. The call is recorded so we handle your claim properly. Is that all right?'

/** A line of speech: English, or French with its English. */
export type Said = string | [fr: string, en: string]
const said = (s: Said): { text: string, en?: string } => (typeof s === 'string' ? { text: s } : { text: s[0], en: s[1] })

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** "19 Dec 2025" for a calendar date. */
export function dayLabel(d: IsoDate): string {
  const [y, m, day] = d.split('-').map(p => Number(p))
  return `${day ?? 1} ${MONTHS[(m ?? 1) - 1] ?? ''} ${y ?? ''}`
}
const money = (v: number): string => `$${v.toLocaleString('en-US')}`
const plusYears = (d: IsoDate, years: number): IsoDate => `${Number(d.slice(0, 4)) + years}${d.slice(4)}`

// ---------------------------------------------------------------- routing spec

export interface SignSpec {
  key: string
  label: string
  evidence: string
  source: SiuIndicator['source']
  /** Turn ref when the sign was heard on the call. */
  turn?: string | null
  weight: number
}

export interface RouteSpec {
  route: Route
  /** What the checks said, when a person changed it. */
  model?: Route
  size: [probability: number, band: 'small' | 'moderate' | 'large', low: number, high: number]
  look: [probability: number, band: 'low' | 'elevated' | 'high']
  reasons: [feature: string, text: string, direction: 'raises' | 'lowers', weight: number, turn: string | null][]
  signs?: SignSpec[]
  rules?: string[]
  override?: { reason: string, by: Who, at: Iso }
  accepted?: { by: Who, at: Iso }
  siu?: { status: SiuReferral['status'], decidedBy?: Who, decidedAt?: Iso, note?: string }
}

const SIZE_LABEL = { small: 'Small', moderate: 'Moderate', large: 'Large' } as const
const LOOK_LABEL = { low: 'No closer look needed', elevated: 'Worth a closer look', high: 'Needs a closer look' } as const
const SIU_STATUS_LABEL: Record<SiuReferral['status'], string> = {
  open: 'Open',
  investigating: 'Investigating',
  closed_no_concern: 'Closed, no concern',
  returned_to_adjuster: 'Returned to the adjuster',
}

// ---------------------------------------------------------------- claim spec

export interface ClaimSpec {
  n: number
  number: string
  holder: string
  lang: Lang
  region: RegionCode
  place: string
  line: 'auto' | 'property'
  lossType: LossKey
  lossDay: number
  policyNumber: string
  status: ClaimStatus
  assignee: Who | null
  /** Local time the call ended, [dayOffset, "h:mm:ss"] in the region's zone (the claim's reported time). */
  end: [number, string]
  surge?: boolean
  description: Said
  short: string
  links: [phrase: string, turn: string][]
  checked?: { by: Who, at: Iso }
  nextSteps: string[]
  photos: [Scene, string][]
  /** Minutes after the call ended when the first photo arrived. */
  photosAfter?: number
  routing: RouteSpec
  sms?: { token: string, body: string, to: string, turn: string }
  lineLabel?: string | null
  flags?: (talk: Talk, startedAt: Iso) => Flag[]
  moments?: (talk: Talk) => Moment[]
  hushes?: [number, number][]
  duration?: number
  timelineExtras?: Omit<CallEvent, 'id' | 'at'>[]
}

export interface ClaimBuild {
  claim: Claim
  call: CallDetail
  talk: Talk
  transcript: Transcript
  recording: Recording
  photos: Photo[]
  routing: RoutingDecision
  siu: SiuReferral | null
  timeline: CallEvent[]
  messages: SmsMessage[]
}

export const claimId = (n: number): string => uid('claim', n)
export const claimCallNo = (n: number): number => 10 + n
export const claimCallId = (n: number): string => uid('call', claimCallNo(n))
const policyNo = (n: number): number => 200 + n

export function buildClaim(c: Clock, s: ClaimSpec, talk: Talk, sections: ClaimFileSection[]): ClaimBuild {
  const tz = tzFor(s.region)
  const id = claimId(s.n)
  const callId = claimCallId(s.n)
  const endedAt = c.atIso(s.end[0], s.end[1], tz)
  const duration = s.duration ?? talk.endSeconds + 1
  const startedAt = c.plus(endedAt, -duration)
  const currency = s.region.startsWith('US') ? 'USD' : 'CAD'
  const lossDate = c.date(s.lossDay, tz)
  const decidedAt = c.plus(endedAt, 20)

  // where it goes
  const r = s.routing
  const severity: ScoreBand = {
    probability: r.size[0],
    band: r.size[1],
    label: `Likely size: ${SIZE_LABEL[r.size[1]]}`,
    detail: `Claims like this usually settle at ${money(r.size[2])} to ${money(r.size[3])}`,
    settleRange: { low: r.size[2], high: r.size[3], currency },
  }
  const signs: SiuIndicator[] = (r.signs ?? []).map(g => ({
    key: g.key,
    label: g.label,
    evidence: g.evidence,
    source: g.source,
    sourceLabel: g.turn ? `▸ ${fmt(talk.sec(g.turn))}` : g.source === 'policy' ? 'from the policy' : g.source === 'weather' ? 'weather record' : g.source === 'claim_history' ? 'claim history' : 'from the call',
    turnId: g.turn ? talk.t(g.turn).id : null,
    atSeconds: g.turn ? talk.sec(g.turn) : null,
    weight: g.weight,
  }))
  const fraud: ScoreBand = {
    probability: r.look[0],
    band: r.look[1],
    label: LOOK_LABEL[r.look[1]],
    detail: signs.length ? `${signs.length} of the 14 signs we check` : 'None of the 14 signs we check',
    settleRange: null,
  }
  const reasons: Reason[] = r.reasons.map(([feature, text, direction, weight, turn]) => ({
    feature, text, direction, weight, turnId: turn ? talk.t(turn).id : null, atSeconds: turn ? talk.sec(turn) : null,
  }))
  const modelRoute = r.model ?? r.route
  const routing: RoutingDecision = {
    claimId: id,
    route: r.route,
    routeLabel: ROUTE_LABEL[r.route],
    modelRoute,
    decidedAt,
    severity,
    fraud,
    reasons,
    signs,
    signsChecked: 14,
    acceptedBy: r.accepted ? ref(r.accepted.by) : null,
    acceptedAt: r.accepted?.at ?? null,
    rulesApplied: r.rules ?? [],
    modelVersions: { size: 'v4', closerLook: 'v4' },
    override: r.override ? { route: r.route, reason: r.override.reason, by: ref(r.override.by), at: r.override.at } : null,
    statement: ROUTING_STATEMENT,
  }
  const siu: SiuReferral | null = r.siu
    ? {
        id: uid('siu', s.n),
        claimId: id,
        claimNumber: s.number,
        status: r.siu.status,
        statusLabel: SIU_STATUS_LABEL[r.siu.status],
        openedAt: decidedAt,
        score: r.look[0],
        indicators: signs,
        decidedBy: r.siu.decidedBy ? ref(r.siu.decidedBy) : null,
        decidedAt: r.siu.decidedAt ?? null,
        note: r.siu.note ?? null,
        statement: SIU_STATEMENT,
      }
    : null

  // photos
  const firstPhoto = c.plus(endedAt, (s.photosAfter ?? 12) * 60)
  const photos: Photo[] = s.photos.map(([scene, caption], i) => {
    const url = sceneUrl(scene, s.n + i)
    return {
      id: uid('photo', s.n * 10 + i + 1),
      url,
      thumbnailUrl: url,
      caption,
      receivedAt: c.plus(firstPhoto, i * 40),
      source: 'text_link',
      width: 400,
      height: 300,
    }
  })

  // the call
  const flags: Flag[] = s.flags ? s.flags(talk, startedAt) : []
  for (const t of talk.turns) {
    if (t.redactions > 0 && !flags.some(f => f.kind === 'card_number_removed')) {
      flags.push(flag('card_number_removed', 'Card number stopped', `Caller started reading a card at ${fmt(t.atMs / 1000)}. Not kept.`, 'info', c.plus(startedAt, t.atMs / 1000), t))
    }
  }
  if (siu && !flags.some(f => f.kind === 'siu_signal')) {
    flags.push(flag('siu_signal', 'Signs worth a closer look', `${signs.length} of the 14 signs we check`, 'warning', decidedAt))
  }
  if (s.surge && !flags.some(f => f.kind === 'surge')) flags.push(flag('surge', 'In the surge', 'Chinook windstorm, Calgary', 'info', startedAt))

  const consentTurn = talk.turns.find(t => t.stage === 'consent' && t.speaker === 'caller') ?? null
  const desc = said(s.description)
  const call = callDetail(c, {
    n: claimCallNo(s.n), startedAt, endedAt, state: 'ended', language: s.lang, callerLabel: s.holder, region: s.region,
    place: s.place, lossType: s.lossType, outcome: 'claim_created', claimId: id, claimNumber: s.number, flags,
    stage: stage('ended'), consentTurn, policyNo: policyNo(s.n), policyNumber: s.policyNumber,
    summary: desc.text, summaryEn: desc.en ?? null, recordingAvailable: true, surgeId: s.surge ? uid('surge', 1) : null,
    lineLabel: s.lineLabel ?? null,
  })

  // recording
  const localEnd = c.date(s.end[0], tz)
  const moments = s.moments ? s.moments(talk) : defaultMoments(talk, photos.length > 0)
  const recording = recordingFrom(talk, {
    seed: 1000 + s.n * 17,
    moments,
    hushes: s.hushes,
    duration,
    audioUrl: null,
    retainedUntil: plusYears(localEnd, 7),
  })

  // in short
  const links = s.links.map(([phrase, turn]) => {
    const start = s.short.indexOf(phrase)
    if (start < 0) throw new Error(`Seed: "${phrase}" is not in the summary of ${s.number}`)
    return { start, end: start + phrase.length, turnId: talk.t(turn).id, atSeconds: talk.sec(turn) }
  })

  const file = claimFile(callId, id, s.lossType, LOSS_LABEL[s.lossType], sections)
  const topReason = r.override ? r.override.reason : (reasons[0]?.text ?? '')
  const claim: Claim = {
    id,
    claimNumber: s.number,
    status: s.status,
    statusLabel: STATUS_LABEL[s.status],
    line: s.line,
    lossType: s.lossType,
    lossTypeLabel: LOSS_LABEL[s.lossType],
    lossDate,
    lossPlace: s.place,
    holderName: s.holder,
    policyNumber: s.policyNumber,
    regionLabel: REGION_LABEL[s.region],
    language: s.lang,
    reportedAt: endedAt,
    route: { route: r.route, label: ROUTE_LABEL[r.route], decidedBy: r.override ? 'person' : 'model', topReason },
    urgentSafety: flags.some(f => f.kind === 'urgent_safety'),
    siuOpen: siu != null && (siu.status === 'open' || siu.status === 'investigating'),
    photos: photos.length,
    assignedTo: s.assignee ? ref(s.assignee) : null,
    surgeLabel: s.surge ? 'Chinook windstorm, Calgary' : null,
    isSample: true,
    callId,
    policyId: uid('policy', policyNo(s.n)),
    holderId: uid('holder', policyNo(s.n)),
    description: desc.text,
    descriptionEn: desc.en ?? null,
    inShort: { text: s.short, links, checkedBy: s.checked ? ref(s.checked.by) : null, checkedAt: s.checked?.at ?? null },
    flags,
    file,
    nextSteps: s.nextSteps,
    recordingAvailable: true,
  }

  // timeline and texts
  const extras: Omit<CallEvent, 'id' | 'at'>[] = [...(s.timelineExtras ?? [])]
  if (consentTurn) extras.push({ atMs: consentTurn.endMs, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } })
  const found = talk.turns.find(t => t.stage === 'identity' && t.speaker === 'caller')
  if (found) extras.push({ atMs: found.endMs + 200, kind: 'tool', label: 'Policy found in 0.2 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } })
  const messages: SmsMessage[] = []
  if (s.sms) {
    const t = talk.t(s.sms.turn)
    extras.push({ atMs: t.atMs + 2000, kind: 'photo_link', label: `Photo link texted to ${s.sms.to}`, actor: 'ClaimVoice', data: { token: s.sms.token } })
    messages.push({ id: uid('sms', claimCallNo(s.n)), toMasked: s.sms.to, body: s.sms.body, sentAt: c.plus(startedAt, t.atMs / 1000 + 2), status: 'sent' })
  }
  extras.push({ atMs: duration * 1000, kind: 'ended', label: `Call ended · claim ${s.number} created`, actor: 'ClaimVoice', data: { claimNumber: s.number } })
  const timeline = timelineFrom(talk, startedAt, c, extras)

  return {
    claim,
    call,
    talk,
    transcript: { callId, language: s.lang, retained: true, notice: null, turns: talk.turns },
    recording,
    photos,
    routing,
    siu,
    timeline,
    messages,
  }
}

function defaultMoments(talk: Talk, hasPhotos: boolean): Moment[] {
  const list: Moment[] = []
  const consent = talk.turns.find(t => t.stage === 'consent' && t.speaker === 'caller')
  if (consent) list.push({ kind: 'consent', label: 'Consent', atSeconds: Math.floor(consent.atMs / 1000), turnId: consent.id })
  const tryRef = (r: string, kind: Moment['kind'], label: string) => {
    try { list.push(moment(kind, label, talk, r)) } catch { /* this call has no such turn */ }
  }
  tryRef('safety', 'policy', 'Policy')
  for (const t of talk.turns) {
    if (t.redactions > 0) list.push({ kind: 'safety', label: 'Card number stopped', atSeconds: Math.floor(t.atMs / 1000), turnId: t.id })
  }
  if (hasPhotos) tryRef('close', 'photos', 'Photo link')
  tryRef('readback', 'read_back', 'Read-back')
  tryRef('close', 'claim_number', 'Claim number')
  return list.sort((a, b) => a.atSeconds - b.atSeconds)
}

// ---------------------------------------------------------------- the light call template

export type RowSrc = [turn: string, phrase: string] | 'policy' | 'tool' | 'pending' | { by: Who }
export type Row = [key: string, label: string, display: string, src: RowSrc, opts?: SlotOpts]

export interface LightSpec extends Omit<ClaimSpec, 'routing'> {
  first: string
  /** French address for the found-you line: "madame Tremblay". */
  frName?: string
  fem?: boolean
  policyPhrase: string
  consentReply?: Said
  policyReply: Said
  story: Said
  ask: Said
  answer: Said
  /** null = the line skipped the read-back (a quality miss). */
  readback: Said | null
  close: Said
  /** Replaces the whole template when a call went differently (keep the same refs). */
  lines?: Line[]
  insured: string
  coverage: string
  deductible: string
  safe: [phrase: string, display: string, value?: boolean]
  facts: Row[]
  factsLabel?: string
  routing: RouteSpec
}

function lightLines(s: LightSpec): Line[] {
  if (s.lines) return s.lines
  const fr = s.lang === 'fr'
  const L = (who: Line['who'], stg: string, ref: string, v: Said): Line => ({ who, stage: stg, ref, ...said(v) })
  const lines: Line[] = [
    fr ? { who: 'line', stage: 'consent', ref: 'consent_ask', text: GREETING_FR, en: GREETING_FR_EN } : { who: 'line', stage: 'consent', ref: 'consent_ask', text: GREETING_EN },
    L('caller', 'consent', 'consent', s.consentReply ?? (fr ? ['Oui, ça me va.', 'Yes, that\'s fine.'] : 'Yes, that\'s fine.')),
    L('line', 'identity', 'policy_ask', fr
      ? ['Merci. Quel est votre numéro de police, ou le numéro de téléphone inscrit à votre police?', 'Thank you. What\'s your policy number, or the phone number on your policy?']
      : 'Thank you. What\'s your policy number, or the phone number on your policy?'),
    L('caller', 'identity', 'policy', s.policyReply),
    L('line', 'safety', 'safety', fr
      ? [`Je vous ai trouvé${s.fem ? 'e' : ''}, ${s.frName ?? s.first}. Avant tout : est-ce que tout le monde est en sécurité?`, `Found you, ${(s.frName ?? s.first).replace('madame', 'Mrs').replace('monsieur', 'Mr')}. Before anything else: is everyone safe?`]
      : `Found it, ${s.first}. Before anything else: is everyone safe right now?`),
    L('caller', 'loss_type', 'story', s.story),
    L('line', 'loss_details', 'ask', s.ask),
    L('caller', 'loss_details', 'answer', s.answer),
  ]
  if (s.readback) {
    lines.push(L('line', 'read_back', 'readback', s.readback))
    lines.push(L('caller', 'read_back', 'confirm', fr ? ['Oui, c\'est exact.', 'Yes, that\'s right.'] : 'Yes, that\'s right.'))
  } else {
    lines.push(L('line', 'read_back', 'noreadback', 'Thanks, I have what I need.'))
    lines.push(L('caller', 'read_back', 'confirm', 'Okay.'))
  }
  lines.push(L('line', 'wrap_up', 'close', s.close))
  return lines
}

function rowSlot(talk: Talk, [key, label, display, src, opts]: Row) {
  if (src === 'policy') return slot(key, label, display, fromPolicy(), opts)
  if (src === 'tool') return slot(key, label, display, lookedUp(), opts)
  if (src === 'pending') return slot(key, label, '', notYet('Waiting on the customer'), opts)
  if (!Array.isArray(src)) return slot(key, label, display, editedBy(src.by), opts)
  return slot(key, label, display, heard(talk, src[0], src[1]), opts)
}

export function lightSections(talk: Talk, s: LightSpec, photos: number): ClaimFileSection[] {
  return [
    section('policy', 'Policy verified', [
      slot('policy_number', 'Policy', `${s.policyNumber} · ${s.holder}`, heard(talk, 'policy', s.policyPhrase)),
      slot('identity_check', 'Identity', 'Passed', lookedUp()),
      slot('insured_item', s.line === 'auto' ? 'Vehicle' : 'Home', s.insured, fromPolicy()),
    ]),
    section('safety', 'People and safety', [
      slot('injury_reported', 'Anyone hurt', s.safe[1], heard(talk, 'story', s.safe[0]), { value: s.safe[2] ?? false }),
    ]),
    section('loss', s.factsLabel ?? 'What happened', s.facts.map(row => rowSlot(talk, row))),
    section('photos', 'Photos', [
      slot('photos_promised', 'Photos', photos ? `${photos} received from the text link` : 'Link sent, none yet', lookedUp('from the text link'), { required: false }),
    ]),
    section('coverage', 'Coverage basics', [
      slot('coverage_lines_mentioned', 'Covered', s.coverage, fromPolicy()),
      slot('deductible_mentioned', 'Deductible', s.deductible, fromPolicy()),
    ]),
  ]
}

export function buildLightClaim(c: Clock, s: LightSpec): ClaimBuild {
  const talk = new Talk(claimCallId(s.n), claimCallNo(s.n), s.lang, s.holder, lightLines(s))
  return buildClaim(c, s, talk, lightSections(talk, s, s.photos.length))
}
