// Shared builders for calls: CallDetail, consent, flags and the live-line view of a call.
import type {
  CallDetail, CallMode, CallSummary, Consent, Flag, FlagKind, HandoffInfo, HeardPillInfo, Iso, Lang, LineState,
  Listener, LiveLine, Mood, StageInfo, Turn,
} from '~/types/api'
import { type Clock, SCRIPTED_PATH, TZ, uid } from './kit'
import { LOSS_LABEL, type LossKey, REGION_LABEL, REGIONS, type RegionCode } from './settings'

export const STATE_LABEL: Record<LineState, string> = {
  ringing: 'Ringing',
  with_line: 'With ClaimVoice',
  waiting_for_person: 'Waiting for a person',
  with_person: 'With a person',
  wrapping_up: 'Wrapping up',
  ended: 'Ended',
}

export const OUTCOME_LABEL: Record<CallSummary['outcome'], string> = {
  claim_created: 'Claim created',
  handed_off: 'Handed to a person',
  abandoned: 'Caller hung up',
  no_claim: 'No claim',
  in_progress: 'On the line',
}

const CONSENT_LABEL: Record<Consent['answer'], string> = {
  given: 'Caller agreed',
  refused: 'Caller said no',
  not_required: 'Announced',
  pending: 'Not asked yet',
}

export function flag(kind: FlagKind, label: string, detail: string, severity: Flag['severity'], at: Iso, turn?: Turn | null): Flag {
  return { kind, label, detail, severity, at, turnId: turn?.id ?? null }
}

export function tzFor(region: RegionCode): number {
  return region === 'CA-QC' ? TZ.montreal : TZ.calgary
}

/** "C-260108-031": the call reference shown on quality and call lists. */
export function callReference(startedAt: Iso, n: number, region: RegionCode): string {
  const local = new Date(new Date(startedAt).getTime() + tzFor(region) * 3600_000).toISOString()
  return `C-${local.slice(2, 4)}${local.slice(5, 7)}${local.slice(8, 10)}-${String(n).padStart(3, '0')}`
}

export interface CallSpec {
  n: number
  startedAt: Iso
  endedAt: Iso | null
  state: LineState
  language: Lang
  callerLabel: string
  region: RegionCode
  place: string | null
  lossType: LossKey | null
  outcome: CallSummary['outcome']
  claimId?: string | null
  claimNumber?: string | null
  flags?: Flag[]
  qaScore?: number | null
  stage: StageInfo
  consentTurn: Turn | null
  consentAnswer?: Consent['answer']
  policyNo: number | null
  policyNumber: string | null
  handoff?: HandoffInfo | null
  listeners?: Listener[]
  summary?: string | null
  summaryEn?: string | null
  recordingAvailable?: boolean
  surgeId?: string | null
  lineLabel?: string | null
  mode?: CallMode
}

export function callDetail(c: Clock, s: CallSpec): CallDetail {
  const region = REGIONS.find(r => r.code === s.region)
  const allParty = region?.consentRule === 'all_party'
  const answer = s.consentAnswer ?? (s.consentTurn ? 'given' : 'pending')
  const duration = s.endedAt ? Math.round((new Date(s.endedAt).getTime() - new Date(s.startedAt).getTime()) / 1000) : null
  return {
    id: uid('call', s.n),
    reference: callReference(s.startedAt, s.n, s.region),
    startedAt: s.startedAt,
    endedAt: s.endedAt,
    durationSeconds: duration,
    state: s.state,
    stateLabel: STATE_LABEL[s.state],
    mode: s.mode ?? 'voice',
    language: s.language,
    callerLabel: s.callerLabel,
    regionLabel: REGION_LABEL[s.region],
    lossTypeLabel: s.lossType ? LOSS_LABEL[s.lossType] : null,
    outcome: s.outcome,
    outcomeLabel: OUTCOME_LABEL[s.outcome],
    claimId: s.claimId ?? null,
    claimNumber: s.claimNumber ?? null,
    flags: s.flags ?? [],
    qaScore: s.qaScore ?? null,
    isSample: true,
    stage: s.stage,
    stages: SCRIPTED_PATH,
    consent: {
      rule: allParty ? 'all_party' : 'one_party',
      ruleLabel: `${allParty ? 'All-party' : 'One-party'} consent (${REGION_LABEL[s.region]})`,
      region: s.region,
      answer,
      answerLabel: CONSENT_LABEL[answer],
      recording: answer !== 'refused',
      askedAt: s.consentTurn ? c.plus(s.startedAt, s.consentTurn.atMs / 1000) : null,
      turnId: s.consentTurn?.id ?? null,
    },
    policyId: s.policyNo != null ? uid('policy', s.policyNo) : null,
    policyNumber: s.policyNumber,
    holderId: s.policyNo != null ? uid('holder', s.policyNo) : null,
    handoff: s.handoff ?? null,
    listeners: s.listeners ?? [],
    summary: s.summary ?? null,
    summaryEn: s.summaryEn ?? null,
    recordingAvailable: s.recordingAvailable ?? s.state === 'ended',
    surgeId: s.surgeId ?? null,
    lineLabel: s.lineLabel ?? null,
    place: s.place,
  }
}

export interface LiveExtras {
  mood: Mood
  heard: HeardPillInfo[]
  lastAsked: { text: string, textEn: string | null } | null
  claimFileProgress: number
  callerVerified: boolean
  callerPhoneMasked: string | null
}

export function liveLine(call: CallDetail, region: RegionCode, lossType: LossKey | null, x: LiveExtras): LiveLine {
  return {
    callId: call.id,
    lineLabel: call.lineLabel ?? 'Line',
    state: call.state,
    stateLabel: call.stateLabel,
    stage: call.stage,
    mode: call.mode,
    language: call.language,
    callerLabel: call.callerLabel,
    callerVerified: x.callerVerified,
    callerPhoneMasked: x.callerPhoneMasked,
    region,
    regionLabel: REGION_LABEL[region],
    lossType,
    lossTypeLabel: lossType ? LOSS_LABEL[lossType] : null,
    answeredAt: call.startedAt,
    flags: call.flags,
    mood: x.mood,
    handoff: call.handoff,
    listeners: call.listeners,
    inSurge: call.surgeId != null,
    lastAsked: x.lastAsked,
    place: call.place ?? null,
    heard: x.heard,
    claimFileProgress: x.claimFileProgress,
    isSample: true,
  }
}
