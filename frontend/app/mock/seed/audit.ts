// The activity log (5 to 8 January, newest first) and the photo links callers open on their phones.
import type { AuditEntry, PhotoLinkInfo } from '~/types/api'
import { claimCallId, claimId } from './claimkit'
import { type Clock, P, TZ, uid, type Who } from './kit'
import { LIVE, SURGE_ID, SURGE_TITLE } from './live'

type Target = [type: string, id: string, label: string] | null

interface Row { day: number, time: string, actor: Who | 'ClaimVoice', action: string, actionLabel: string, target: Target, summary: string, details?: Record<string, unknown> }

export function buildAudit(c: Clock, refs: { unverifiedCallId: string, unverifiedRef: string }): AuditEntry[] {
  const claim = (n: number, number: string): Target => ['claim', claimId(n), number]
  const signIn = (day: number, time: string, who: Who): Row =>
    ({ day, time, actor: who, action: 'auth.login', actionLabel: 'signed in', target: null, summary: `${who.name} signed in.` })
  const gordAt = c.clockLabel(c.iso(-192 + 151))

  const rows: Row[] = [
    // Monday 5 January
    signIn(-3, '8:02', P.priya),
    signIn(-3, '8:31', P.renee),
    { day: -3, time: '10:30', actor: P.priya, action: 'check.regulator_pack', actionLabel: 'downloaded the pack for the regulator', target: null, summary: 'Priya Sandhu downloaded the pack for the regulator after the monthly review.' },
    { day: -3, time: '11:05', actor: P.nadia, action: 'settings.script', actionLabel: 'changed a script', target: ['script', 'wind', 'Wind script'], summary: 'Nadia Kassem added two storm questions to the Wind script (version 4).', details: { version: 4 } },
    { day: -3, time: '14:20', actor: P.dev, action: 'siu.decision', actionLabel: 'started an investigation', target: claim(15, 'CV-25-01733'), summary: 'Dev Malhotra started an investigation on CV-25-01733: "Asked for the police file number and the dealer\'s key records."', details: { decision: 'investigate' } },
    // Tuesday 6 January
    signIn(-2, '8:12', P.renee),
    { day: -2, time: '9:40', actor: P.renee, action: 'check.signed_off', actionLabel: 'signed off', target: ['check', 'closer_look', 'Closer-look check, version 5'], summary: 'Renée Kowalchuk signed off Closer-look check version 5 for claims.', details: { side: 'claims', version: 5 } },
    { day: -2, time: '10:15', actor: P.renee, action: 'qa.review', actionLabel: 'reviewed call quality', target: ['call', refs.unverifiedCallId, `${refs.unverifiedRef} (Unverified caller)`], summary: `Renée Kowalchuk reviewed the call quality of ${refs.unverifiedRef} (Unverified caller) and agreed with every item.` },
    { day: -2, time: '13:04', actor: P.nadia, action: 'invitation.created', actionLabel: 'invited', target: ['invitation', uid('invite', 1), 'tanvir.ahmed@larkspurmutual.ca'], summary: 'Nadia Kassem invited tanvir.ahmed@larkspurmutual.ca to join as an intake agent.', details: { role: 'intake_agent' } },
    { day: -2, time: '13:30', actor: P.aurelie, action: 'recording.played', actionLabel: 'played the recording', target: claim(11, 'CV-25-01781'), summary: 'Aurélie Fortin played the recording of CV-25-01781.' },
    { day: -2, time: '16:45', actor: P.nadia, action: 'settings.handoff', actionLabel: 'changed the hand-off rules', target: ['settings', 'handoff', 'Hand-off rules'], summary: 'Nadia Kassem changed the hand-off rules: offer a call-back after 90 seconds without a person.', details: { maxWaitSeconds: { from: 120, to: 90 } } },
    { day: -2, time: '16:52', actor: P.nadia, action: 'retention.deletion_requested', actionLabel: 'logged a deletion request', target: ['settings', 'retention', 'Retention'], summary: 'Nadia Kassem logged a deletion request from a former policyholder. Two requests are waiting.' },
    // Wednesday 7 January
    signIn(-1, '8:05', P.lena),
    { day: -1, time: '9:20', actor: P.renee, action: 'claim.assigned', actionLabel: 'assigned', target: claim(12, 'CV-25-01768'), summary: 'Renée Kowalchuk assigned CV-25-01768 to Lena Ortiz.', details: { to: P.lena.id } },
    { day: -1, time: '10:40', actor: P.owen, action: 'qa.review', actionLabel: 'reviewed call quality', target: claim(12, 'CV-25-01768'), summary: 'Owen Fairweather reviewed the call quality of CV-25-01768 and agreed that kind words were missing.' },
    { day: -1, time: '11:32', actor: P.nadia, action: 'invitation.created', actionLabel: 'invited', target: ['invitation', uid('invite', 2), 'claire.beaulieu@larkspurmutual.ca'], summary: 'Nadia Kassem invited claire.beaulieu@larkspurmutual.ca to join as an adjuster.', details: { role: 'adjuster' } },
    { day: -1, time: '14:00', actor: P.aurelie, action: 'claim.status_changed', actionLabel: 'changed the status', target: claim(7, 'CV-26-01829'), summary: 'Aurélie Fortin moved CV-26-01829 to Waiting on the customer.', details: { from: 'in_review', to: 'waiting_on_customer' } },
    { day: -1, time: '16:50', actor: P.sofia, action: 'claim.file_edited', actionLabel: 'edited the claim file', target: claim(6, 'CV-26-01833'), summary: 'Sofía Herrera corrected where it happened on CV-26-01833.', details: { field: 'loss_place' } },
    { day: -1, time: '20:00', actor: 'ClaimVoice', action: 'surge.started', actionLabel: 'started a surge', target: ['surge', SURGE_ID, SURGE_TITLE], summary: 'A wind warning for Calgary and Airdrie started the surge "Chinook windstorm, Calgary".' },
    { day: -1, time: '20:06', actor: P.renee, action: 'surge.questions', actionLabel: 'switched on surge questions', target: ['surge', SURGE_ID, SURGE_TITLE], summary: 'Renée Kowalchuk switched on wind questions for Chinook windstorm, Calgary.', details: { on: true } },
    // Thursday 8 January
    signIn(0, '5:58', P.renee),
    { day: 0, time: '6:02', actor: P.renee, action: 'surge.standby_notified', actionLabel: 'put the standby team on notice', target: ['surge', SURGE_ID, SURGE_TITLE], summary: 'Renée Kowalchuk put the standby team (2) on notice for Chinook windstorm, Calgary.' },
    { day: 0, time: '6:18:40', actor: P.jamal, action: 'call.handoff_accepted', actionLabel: 'took a hand-off', target: ['call', claimCallId(4), 'Line 2 (Arjun Bains)'], summary: 'Jamal Haddad took the hand-off from Line 2 (Arjun Bains) at 6:18 a.m.' },
    { day: 0, time: '6:47:20', actor: 'ClaimVoice', action: 'claim.routed', actionLabel: 'routed a claim', target: claim(2, 'CV-26-01856'), summary: 'The routing checks sent CV-26-01856 to Closer look and opened a referral for special investigations.', details: { route: 'special_investigation', signs: 3 } },
    signIn(0, '7:12', P.lena),
    { day: 0, time: '7:20', actor: P.lena, action: 'recording.played', actionLabel: 'played the recording', target: claim(2, 'CV-26-01856'), summary: 'Lena Ortiz played the recording of CV-26-01856.' },
    { day: 0, time: '7:26', actor: P.lena, action: 'claim.route_override', actionLabel: 'changed the route', target: claim(2, 'CV-26-01856'), summary: 'Lena Ortiz changed the route of CV-26-01856 from Closer look to Adjuster: "Police report confirms the SUV."', details: { from: 'special_investigation', to: 'adjuster', reason: 'Police report confirms the SUV.' } },
    { day: 0, time: '7:28', actor: P.lena, action: 'claim.file_edited', actionLabel: 'edited the claim file', target: claim(2, 'CV-26-01856'), summary: 'Lena Ortiz updated the other car on CV-26-01856 from the police report.', details: { field: 'other_party_vehicle' } },
    { day: 0, time: '7:30', actor: P.owen, action: 'qa.review', actionLabel: 'reviewed call quality', target: claim(3, 'CV-26-01853'), summary: 'Owen Fairweather reviewed the call quality of CV-26-01853 and agreed with every item.' },
    signIn(0, '7:33', P.priya),
    { day: 0, time: '7:36', actor: P.dev, action: 'recording.played', actionLabel: 'played the recording', target: claim(2, 'CV-26-01856'), summary: 'Dev Malhotra played the recording of CV-26-01856.' },
    { day: 0, time: '7:40', actor: P.renee, action: 'call.listen', actionLabel: 'started listening', target: ['call', LIVE.martine.callId, 'Line 3 (Martine Gagnon)'], summary: 'Renée Kowalchuk started listening to Line 3 (Martine Gagnon) at 7:40 a.m.' },
    { day: 0, time: '7:41:19', actor: P.renee, action: 'call.whisper', actionLabel: 'whispered', target: ['call', LIVE.gord.callId, 'Line 1 (Gord Lindqvist)'], summary: `Renée Kowalchuk whispered to Line 1 (Gord Lindqvist) at ${gordAt}: "Ask if the garage skylight is damaged too."`, details: { text: 'Ask if the garage skylight is damaged too.' } },
  ]

  const entries = rows.map((r, i): AuditEntry => {
    const seq = 4101 + i
    return {
      id: uid('audit', seq),
      seq,
      at: c.atIso(r.day, r.time, TZ.calgary),
      actorLabel: r.actor === 'ClaimVoice' ? 'ClaimVoice' : r.actor.name,
      action: r.action,
      actionLabel: r.actionLabel,
      targetType: r.target?.[0] ?? null,
      targetId: r.target?.[1] ?? null,
      targetLabel: r.target?.[2] ?? null,
      summary: r.summary,
      details: r.details ?? {},
    }
  })
  return entries.reverse()
}

export function buildPhotoLinks(c: Clock): Record<string, PhotoLinkInfo> {
  const link = (claimReference: string, language: 'en' | 'fr', expiresAt: string, uploaded: number): PhotoLinkInfo =>
    ({ orgName: 'Larkspur Mutual', claimReference, language, expiresAt, maxPhotos: 10, uploaded })
  const hours72 = 72 * 3600
  return {
    'demo-photos-gord': link('CV-26-01861', 'en', c.iso(hours72), 0),
    'demo-photos-martine': link('CV-26-01863', 'fr', c.iso(-365 + 350 + hours72), 0),
    'photos-cv-26-01856': link('CV-26-01856', 'en', c.plus(c.atIso(0, '6:45', TZ.denver), hours72), 3),
    'photos-cv-26-01842': link('CV-26-01842', 'en', c.plus(c.atIso(0, '2:13'), hours72), 2),
    'photos-cv-26-01851': link('CV-26-01851', 'en', c.plus(c.atIso(0, '6:16'), hours72), 0),
    'expired-link': link('CV-26-01806', 'en', c.plus(c.atIso(-5, '10:20', TZ.denver), hours72), 2),
  }
}
