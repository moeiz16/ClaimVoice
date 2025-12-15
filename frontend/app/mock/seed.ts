// The demo database for the local mock API: Larkspur Mutual on Thursday 8 January 2026 at 7:42 a.m. Calgary time, the
// morning after a Chinook windstorm (docs/DATA.md "Seed plan: Larkspur Mutual"). Every timestamp is computed from `now`,
// so the same story can be replayed at any moment. The pieces live in ./seed/.
import type {
  CallDetail, CallEvent, ClaimSummary, Claim, Photo, QaQueueItem, QaScore, Recording, RoutingDecision, SiuReferral,
  SmsMessage, SwitchboardSnapshot, TodayStats, Transcript,
} from '~/types/api'
import type { MockDb } from './db'
import { buildAudit, buildPhotoLinks } from './seed/audit'
import { buildLightClaim, type ClaimBuild } from './seed/claimkit'
import { lightSpecs } from './seed/claims-light'
import { buildArjun, buildDana, buildTomas } from './seed/claims-rich'
import { CARD, fmt, makeClock, P, ref, uid } from './seed/kit'
import { buildLive } from './seed/live'
import { buildPeople } from './seed/people'
import { buildRosa, buildUnverified, type QaSpec, queueItem, scoreCall } from './seed/quality'
import { buildRouting } from './seed/routing'
import {
  buildConsentRules, buildHandoffRules, buildLanguages, buildMeta, buildPrivacy, buildRetention, buildScripts,
} from './seed/settings'

function toSummary(cl: Claim): ClaimSummary {
  return {
    id: cl.id,
    claimNumber: cl.claimNumber,
    status: cl.status,
    statusLabel: cl.statusLabel,
    line: cl.line,
    lossType: cl.lossType,
    lossTypeLabel: cl.lossTypeLabel,
    lossDate: cl.lossDate,
    lossPlace: cl.lossPlace,
    holderName: cl.holderName,
    policyNumber: cl.policyNumber,
    regionLabel: cl.regionLabel,
    language: cl.language,
    reportedAt: cl.reportedAt,
    route: cl.route,
    urgentSafety: cl.urgentSafety,
    siuOpen: cl.siuOpen,
    photos: cl.photos,
    assignedTo: cl.assignedTo,
    surgeLabel: cl.surgeLabel,
    isSample: cl.isSample,
  }
}

const median = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b)
  if (!s.length) return 0
  const mid = Math.floor(s.length / 2)
  const hi = s[mid] ?? 0
  const lo = s[mid - 1] ?? hi
  return s.length % 2 ? hi : Math.round((lo + hi) / 2)
}

export function buildSeed(now: Date = new Date('2026-01-08T14:42:00Z')): MockDb {
  const c = makeClock(now)
  const people = buildPeople(c)
  const live = buildLive(c)

  // ------------------------------------------------------------ claims (newest first)
  const builds: ClaimBuild[] = [buildTomas(c), buildDana(c), buildArjun(c), ...lightSpecs(c).map(s => buildLightClaim(c, s))]
  builds.sort((a, b) => b.claim.reportedAt.localeCompare(a.claim.reportedAt))
  const byNumber = (number: string): ClaimBuild => {
    const b = builds.find(x => x.claim.claimNumber === number)
    if (!b) throw new Error(`Seed: no claim ${number}`)
    return b
  }

  const rosa = buildRosa(c)
  const unverified = buildUnverified(c)

  // ------------------------------------------------------------ call quality
  const forClaim = (number: string, rest: Omit<QaSpec, 'talk' | 'call' | 'claimId' | 'claimNumber'>): QaSpec => {
    const b = byNumber(number)
    return { talk: b.talk, call: b.call, claimId: b.claim.id, claimNumber: b.claim.claimNumber, ...rest }
  }
  const malik = byNumber('CV-26-01806')
  const consentLate = malik.talk.sec('consent_ask')
  const queued: QaSpec[] = [
    forClaim('CV-26-01806', {
      details: [4, 4],
      status: 'needs_review',
      queued: 'Critical item failed: consent first',
      items: {
        consent_first: {
          passed: false,
          note: `The recording notice came at ${fmt(consentLate)}, after the policy number and the story.`,
          evidence: [['greet', 'What\'s your policy number'], ['consent_ask', 'this call is recorded']],
          at: consentLate,
        },
        consent_rule: { note: 'Colorado allows one-party recording, but our line always gives the notice first.' },
      },
      focus: { atSeconds: consentLate, text: `Jumped to ${fmt(consentLate)}, where the recording notice finally came` },
    }),
    { talk: rosa.talk, call: rosa.call, claimId: null, claimNumber: null, details: [3, 3], status: 'needs_review',
      queued: 'Critical item failed: no card numbers',
      items: {
        required_fields: { passed: null, note: 'No claim was needed on this call.' },
        read_back: { passed: null, note: 'No claim was needed, so there was nothing to read back.' },
        no_card_numbers: {
          passed: false,
          note: 'She read a card number for 9 seconds before ClaimVoice stopped her. It was removed from the recording and the transcript.',
          evidence: [['card', CARD], ['stop', 'Please stop there']],
          at: 57,
        },
      },
      focus: { atSeconds: 57, text: 'Jumped to 0:57, where a card number was read for 9 seconds before ClaimVoice stopped it' },
    },
    forClaim('CV-26-01851', {
      details: [10, 10],
      status: 'needs_review',
      queued: 'A hand-off rule applied: asked for a person',
      items: {
        handoff_correct: {
          passed: false,
          note: 'He asked for a person at 3:30. ClaimVoice asked another question first, and the hand-off came at 4:10, 40 seconds late.',
          evidence: [['ask_person', 'can I just talk to someone'], ['kept_going', 'Can I first check the address for the visit']],
          at: 250,
        },
      },
      focus: { atSeconds: 250, text: 'Jumped to 4:10, where the hand-off came 40 seconds late' },
    }),
    forClaim('CV-26-01817', {
      details: [9, 10],
      status: 'needs_review',
      queued: 'Read-back skipped',
      items: {
        read_back: { passed: false, note: 'ClaimVoice gave the claim number without reading the details back.', evidence: [['noreadback', 'Thanks, I have what I need.']] },
        required_fields: { passed: false, note: '9 of 10 required details: where the car is now is missing.' },
      },
    }),
    forClaim('CV-26-01829', {
      details: [6, 10],
      status: 'needs_review',
      queued: 'Low details: 6 of 10',
      items: { required_fields: { passed: false, note: '6 of 10 required details: the report number, the laptop\'s value, the time and which window are missing.' } },
    }),
    forClaim('CV-25-01768', {
      details: [8, 10],
      status: 'reviewed',
      queued: 'Language check: kind words missing',
      items: {
        empathy: {
          passed: false,
          note: 'He said his wrist hurt; ClaimVoice went straight to the damage without acknowledging it.',
          evidence: [['story', 'my wrist hurts from the airbag'], ['ask', 'What is the damage to your vehicle?']],
        },
        required_fields: { passed: false, note: '8 of 10 required details: the other drivers\' insurers and the tow yard are missing.' },
      },
      review: { by: P.owen, at: c.atIso(-1, '10:40'), note: 'Agree. Coaching note sent to the script owner: acknowledge an injury before asking about damage.' },
    }),
    { talk: unverified.talk, call: unverified.call, claimId: null, claimNumber: null, details: [0, 0], status: 'reviewed',
      queued: 'A hand-off rule applied: identity not confirmed',
      items: {
        identity_verified: {
          passed: false,
          note: 'Could not confirm who she was after two tries; ClaimVoice handed her to a person, as the rules say.',
          evidence: [['postal', 'Can you tell me the postal code on the policy']],
        },
        required_fields: { passed: null, note: 'No claim on this call.' },
        read_back: { passed: null, note: 'No claim on this call.' },
        handoff_correct: { note: 'She asked for a person and was handed over straight away.' },
      },
      review: { by: P.renee, at: c.atIso(-2, '10:15'), note: 'Right call: we never guess a policy for someone else.' },
    },
    forClaim('CV-25-01781', { details: [8, 8], status: 'needs_review', queued: 'Random sample' }),
    forClaim('CV-26-01853', {
      details: [6, 6],
      status: 'reviewed',
      queued: 'Random sample',
      review: { by: P.owen, at: c.atIso(0, '7:30'), note: 'Clean call. Good use of the storm question.' },
    }),
  ]
  const autoPassed: QaSpec[] = [
    forClaim('CV-26-01858', { details: [9, 10], status: 'auto_passed', items: { required_fields: { passed: false, note: '9 of 10 required details: when the leak started is missing.' } } }),
    forClaim('CV-26-01856', { details: [12, 12], status: 'auto_passed' }),
    forClaim('CV-26-01842', { details: [9, 9], status: 'auto_passed' }),
    forClaim('CV-26-01833', { details: [8, 8], status: 'auto_passed' }),
    forClaim('CV-26-01794', { details: [7, 7], status: 'auto_passed' }),
    forClaim('CV-25-01752', { details: [9, 10], status: 'auto_passed', items: { required_fields: { passed: false, note: '9 of 10 required details: when it was found is missing.' } } }),
    forClaim('CV-25-01740', { details: [6, 6], status: 'auto_passed' }),
    forClaim('CV-25-01733', { details: [8, 8], status: 'auto_passed' }),
    forClaim('CV-25-01719', { details: [9, 10], status: 'auto_passed', items: { required_fields: { passed: false, note: '9 of 10 required details: the time it happened is missing.' } } }),
    forClaim('CV-25-01708', { details: [8, 8], status: 'auto_passed' }),
    forClaim('CV-25-01702', { details: [7, 7], status: 'auto_passed' }),
  ]

  const qaScores: Record<string, QaScore> = {}
  const qaQueue: QaQueueItem[] = []
  for (const spec of [...queued, ...autoPassed]) {
    const score = scoreCall(c, spec)
    qaScores[spec.call.id] = score
    spec.call.qaScore = score.score
    if (spec.status !== 'auto_passed') qaQueue.push(queueItem(spec, score))
  }
  const bandOrder = { failed: 0, needs_attention: 1, good: 2 } as const
  qaQueue.sort((a, b) => bandOrder[a.band] - bandOrder[b.band] || a.score - b.score)

  // ------------------------------------------------------------ maps by call and by claim
  const calls: Record<string, CallDetail> = { ...live.calls }
  const transcripts: Record<string, Transcript> = { ...live.transcripts }
  const timelines: Record<string, CallEvent[]> = { ...live.timelines }
  const messages: Record<string, SmsMessage[]> = { ...live.messages }
  const recordings: Record<string, Recording> = {}
  const photos: Record<string, Photo[]> = {}
  const routing: Record<string, RoutingDecision> = {}
  const siu: Record<string, SiuReferral> = {}
  for (const b of builds) {
    calls[b.call.id] = b.call
    transcripts[b.call.id] = b.transcript
    timelines[b.call.id] = b.timeline
    messages[b.call.id] = b.messages
    recordings[b.claim.id] = b.recording
    photos[b.claim.id] = b.photos
    routing[b.claim.id] = b.routing
    if (b.siu) siu[b.claim.id] = b.siu
  }
  const callRecordings: Record<string, Recording> = {}
  for (const loose of [rosa, unverified]) {
    calls[loose.call.id] = loose.call
    transcripts[loose.call.id] = loose.transcript
    timelines[loose.call.id] = loose.timeline
    messages[loose.call.id] = []
    callRecordings[loose.call.id] = loose.recording
  }
  const claims = builds.map(b => b.claim)

  // ------------------------------------------------------------ the line desk
  const startOfToday = c.atIso(0, '0:00')
  const finishedToday = builds.filter(b => b.claim.reportedAt >= startOfToday)
  const callsToday = Object.values(calls).filter(x => x.startedAt >= startOfToday)
  const scoresToday = finishedToday.map(b => qaScores[b.call.id]?.score).filter((s): s is number => s != null)
  const today: TodayStats = {
    callsAnswered: callsToday.length,
    answeredFirstRingShare: 1,
    medianHandleSeconds: median(finishedToday.map(b => b.call.durationSeconds ?? 0)),
    handoffs: callsToday.filter(x => x.handoff != null || transcripts[x.id]?.turns.some(t => t.stage === 'handoff')).length,
    claimsCreated: finishedToday.length,
    averageQaScore: scoresToday.length ? Math.round(scoresToday.reduce((a, s) => a + s, 0) / scoresToday.length) : null,
    surgeCalls: callsToday.filter(x => x.surgeId != null).length,
  }
  const switchboard: SwitchboardSnapshot = {
    lines: live.lines,
    handoffTray: live.handoffTray,
    surge: live.surge,
    recentClaims: finishedToday.slice(0, 8).map(b => toSummary(b.claim)),
    freePeople: [ref(P.jamal), ref(P.sofia), ref(P.aurelie)],
    caption: 'Larkspur Mutual · Thursday 8 January · 7:42 a.m. Calgary time · 3 on the line, 2 waiting for a person',
    today,
    lastEventId: 4200,
  }

  const routingSeed = buildRouting(c)

  return {
    now,
    orgId: uid('org', 1),
    meta: buildMeta(),
    people: people.people,
    demoPeople: people.demoPeople,
    permissions: people.permissions,
    roles: people.roles,
    members: people.members,
    invitations: people.invitations,

    switchboard,
    calls,
    transcripts,
    claimFiles: live.claimFiles,
    timelines,
    messages,
    liveLines: live.liveLines,

    claims,
    recordings,
    callRecordings,
    photos,
    routing,
    siu,

    qaQueue,
    qaScores,

    routingChecks: routingSeed.routingChecks,
    factSheets: routingSeed.factSheets,
    fairness: routingSeed.fairness,
    checks: routingSeed.checks,

    scripts: buildScripts(c),
    consentRules: buildConsentRules(),
    handoffRules: buildHandoffRules(),
    languages: buildLanguages(),
    retention: buildRetention(c),
    privacy: buildPrivacy(),

    audit: buildAudit(c, { unverifiedCallId: unverified.call.id, unverifiedRef: unverified.call.reference }),

    photoLinks: buildPhotoLinks(c),
  }
}
