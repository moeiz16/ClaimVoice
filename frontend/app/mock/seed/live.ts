// The line desk at 7:42 a.m.: three calls on the line (Gord, Kiara, Martine), two waiting for a person (Hal, Wendy),
// and the Chinook windstorm surge (docs/DATA.md "Live at the demo moment").
import type { CallDetail, CallEvent, ClaimFile, HandoffInfo, LiveLine, SmsMessage, Surge, Transcript } from '~/types/api'
import { callDetail, flag, liveLine } from './calls'
import {
  CARD, type Clock, claimFile, fromPolicy, heard, type Line, lookedUp, notYet, P, section, slot, stage, Talk,
  timelineFrom, uid,
} from './kit'

export const LIVE = {
  gord: { n: 1, callId: uid('call', 1), draft: 'CV-26-01861', policy: 'LM-AB-204118', policyNo: 101 },
  kiara: { n: 2, callId: uid('call', 2), draft: 'CV-26-01862', policy: 'LM-CO-311592', policyNo: 102 },
  martine: { n: 3, callId: uid('call', 3), draft: 'CV-26-01863', policy: 'LM-QC-118407', policyNo: 103 },
  hal: { n: 4, callId: uid('call', 4), draft: 'CV-26-01864', policy: 'LM-AB-338420', policyNo: 104 },
  wendy: { n: 5, callId: uid('call', 5), draft: 'CV-26-01860', policy: 'LM-AB-291076', policyNo: 105 },
} as const

export const SURGE_ID = uid('surge', 1)
export const SURGE_TITLE = 'Chinook windstorm, Calgary'
const GREETING = 'Larkspur Mutual claims, this is ClaimVoice, an automated assistant. This call is recorded so we get your claim right. Is that okay?'

export interface LiveSeed {
  calls: Record<string, CallDetail>
  transcripts: Record<string, Transcript>
  claimFiles: Record<string, ClaimFile>
  timelines: Record<string, CallEvent[]>
  messages: Record<string, SmsMessage[]>
  liveLines: Record<string, LiveLine>
  lines: LiveLine[]
  handoffTray: HandoffInfo[]
  surge: Surge
}

const transcript = (talk: Talk): Transcript => ({ callId: talk.callId, language: talk.language, retained: true, notice: null, turns: talk.turns })

export function buildLive(c: Clock): LiveSeed {
  const out: LiveSeed = {
    calls: {}, transcripts: {}, claimFiles: {}, timelines: {}, messages: {}, liveLines: {}, lines: [], handoffTray: [],
    surge: buildSurge(c),
  }
  const surgeFlag = (at: string) => flag('surge', 'In the surge', SURGE_TITLE, 'info', at)

  // ------------------------------------------------------------ Line 1 · Gord Lindqvist · Saddle Ridge, Calgary · wind
  {
    const L = LIVE.gord
    const startedAt = c.iso(-192)
    const lines: Line[] = [
      { who: 'line', at: 0, stage: 'consent', ref: 'greet', text: GREETING },
      { who: 'caller', at: 7, stage: 'consent', ref: 'consent', text: 'Yes, that\'s fine. The wind last night tore up my house.' },
      { who: 'line', at: 11, stage: 'identity', text: 'I\'m sorry to hear that. Let\'s get it sorted. What\'s your policy number, or the phone number on your policy?' },
      { who: 'caller', at: 20, stage: 'identity', ref: 'policy', text: 'Sure, it\'s LM-AB-204118.' },
      { who: 'line', at: 37, stage: 'safety', ref: 'safety', text: 'Found you, Gord, and the number you\'re calling from matches. Before anything else: is everyone safe, and is anything leaking, sparking or smelling of gas?' },
      { who: 'caller', at: 58, stage: 'safety', ref: 'safe', text: 'Everyone\'s okay. Nobody\'s hurt and nothing\'s dangerous, the power\'s still on.' },
      { who: 'line', at: 64, stage: 'loss_type', text: 'Good. Tell me what happened.' },
      {
        who: 'caller', at: 80, end: 134, stage: 'loss_type', ref: 'story',
        text: `It was the Chinook overnight. A bunch of shingles are gone off the roof and the siding on the north side is torn. [dog barking] Oh, and the skylight in the kitchen got smashed by something blown off the neighbour's deck. You want my Visa for the deductible? It's ${CARD}`,
      },
      { who: 'line', at: 136, stage: 'loss_details', ref: 'stop', text: 'Please stop there. I never take card numbers on this line, and that part of the recording is removed. Is the kitchen open to the weather right now?' },
      { who: 'caller', at: 144, stage: 'loss_details', ref: 'tarp', text: 'No, I taped a tarp over the skylight. We can still live here.' },
      { who: 'whisper', at: 151, stage: 'loss_details', ref: 'whisper', label: 'Whisper, ClaimVoice only · Renée', text: 'Ask if the garage skylight is damaged too.' },
      { who: 'line', at: 160, stage: 'loss_details', ref: 'ask', text: 'Good thinking with the tarp. When did the wind do the damage, roughly? And is the skylight over your garage damaged too?' },
      { who: 'caller', at: 178, end: 190, stage: 'loss_details', ref: 'when', conf: 0.71, text: 'I heard a bang around two in the morning. The garage skylight\'s cracked, I think, I\'ll have to check when it\'s light.' },
    ]
    const talk = new Talk(L.callId, L.n, 'en', 'Gord Lindqvist', lines)
    const story = talk.t('story')
    const call = callDetail(c, {
      n: L.n, startedAt, endedAt: null, state: 'with_line', language: 'en', callerLabel: 'Gord Lindqvist', region: 'CA-AB',
      place: 'Saddle Ridge, Calgary', lossType: 'wind', outcome: 'in_progress', stage: stage('loss_details'),
      consentTurn: talk.t('consent'), policyNo: L.policyNo, policyNumber: L.policy, surgeId: SURGE_ID, lineLabel: 'Line 1',
      flags: [
        surgeFlag(startedAt),
        flag('card_number_removed', 'Card number stopped', 'He started reading a card at 1:58. Not kept; 4 seconds cut.', 'info', c.plus(startedAt, 118), story),
      ],
    })
    const file = claimFile(L.callId, null, 'wind', 'Wind', [
      section('policy', 'Policy verified', [
        slot('policy_number', 'Policy', 'LM-AB-204118 · Gord Lindqvist', heard(talk, 'policy', 'LM-AB-204118')),
        slot('identity_check', 'Identity', 'Passed · calling from the number on the policy', lookedUp()),
        slot('insured_item', 'Home', '84 Saddlecrest Way NE, Calgary · Home Comprehensive', fromPolicy()),
      ]),
      section('loss', 'What happened', [
        slot('loss_type', 'Cause', 'Wind (Chinook)', heard(talk, 'story', 'It was the Chinook overnight'), { value: 'wind' }),
        slot('loss_date', 'When', 'Overnight, Wed 7 to Thu 8 Jan', heard(talk, 'consent', 'The wind last night')),
        slot('loss_time', 'About what time', 'About 2 a.m.', heard(talk, 'when', 'around two in the morning'), { conf: 0.72, value: '02:00' }),
        slot('loss_place', 'Where', 'At home, Saddle Ridge, Calgary', fromPolicy()),
      ]),
      section('safety', 'People and safety', [
        slot('injury_reported', 'Anyone hurt', 'No', heard(talk, 'safe', 'Nobody\'s hurt'), { value: false }),
        slot('danger_now', 'Gas, water, power', 'None; power still on', heard(talk, 'safe', 'nothing\'s dangerous, the power\'s still on'), { value: false }),
      ]),
      section('details', 'Damage', [
        slot('roof_or_window_damage', 'Roof', 'Shingles torn off', heard(talk, 'story', 'A bunch of shingles are gone off the roof'), { value: true }),
        slot('siding_or_fence_damage', 'Siding', 'Torn on the north side', heard(talk, 'story', 'the siding on the north side is torn'), { value: true }),
        slot('skylight_damage', 'Kitchen skylight', 'Smashed by blown debris', heard(talk, 'story', 'the skylight in the kitchen got smashed'), { value: true }),
        slot('debris_source', 'Debris from', 'Neighbour\'s deck', heard(talk, 'story', 'blown off the neighbour\'s deck'), { required: false }),
        slot('mitigation_taken', 'Covered up', 'Tarp taped over the skylight', heard(talk, 'tarp', 'I taped a tarp over the skylight'), { value: true }),
        slot('home_livable', 'Home livable', 'Yes', heard(talk, 'tarp', 'We can still live here'), { value: true }),
        slot('garage_skylight', 'Garage skylight', 'Cracked, he thinks', heard(talk, 'when', 'The garage skylight\'s cracked, I think'), { conf: 0.52, required: false }),
        slot('card_number_moment', 'Card numbers', 'He started one at 1:58. Not kept; 4 seconds cut.', lookedUp('removed'), { required: false }),
      ]),
      section('photos', 'Photos', [
        slot('photos_promised', 'Link', '', notYet('Next step')),
      ]),
      section('coverage', 'Coverage basics', [
        slot('coverage_lines_mentioned', 'Wind', 'Covered: roof, siding and skylights under Home Comprehensive', fromPolicy()),
        slot('deductible_mentioned', 'Deductible', '$1,000 home', fromPolicy()),
      ]),
    ])
    out.calls[L.callId] = call
    out.transcripts[L.callId] = transcript(talk)
    out.claimFiles[L.callId] = file
    out.messages[L.callId] = []
    out.timelines[L.callId] = timelineFrom(talk, startedAt, c, [
      { atMs: 1000, kind: 'flag', label: 'In the Chinook windstorm surge: wind questions on', actor: 'ClaimVoice', data: { kind: 'surge' } },
      { atMs: 7600, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
      { atMs: 22400, kind: 'tool', label: 'Policy found in 0.2 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } },
      { atMs: 151000, kind: 'whisper', label: 'Renée Kowalchuk whispered: "Ask if the garage skylight is damaged too."', actor: P.renee.name, data: { text: 'Ask if the garage skylight is damaged too.' } },
    ])
    const line = liveLine(call, 'CA-AB', 'wind', {
      mood: { key: 'calm', label: 'Sounds calm', detail: 'card number stopped' },
      heard: [
        { key: 'policy', text: 'Policy LM-AB-204118 ✓', tone: 'normal' },
        { key: 'roof', text: 'Shingles torn off', tone: 'normal' },
        { key: 'skylight', text: 'Skylight smashed by debris', tone: 'normal' },
        { key: 'hurt', text: 'Nobody hurt', tone: 'normal' },
      ],
      lastAsked: { text: 'When did the wind do the damage, roughly?', textEn: null },
      claimFileProgress: file.progress,
      callerVerified: true,
      callerPhoneMasked: '•••-•••-0142',
    })
    out.liveLines[L.callId] = line
    out.lines.push(line)
  }

  // ------------------------------------------------------------ Line 2 · Kiara Booker · Colfax Ave, Denver · rear-ended
  {
    const L = LIVE.kiara
    const startedAt = c.iso(-108)
    const talk = new Talk(L.callId, L.n, 'en', 'Kiara Booker', [
      { who: 'line', at: 0, stage: 'greeting', text: 'Larkspur Mutual claims, this is ClaimVoice, an automated assistant. What can I help you with?' },
      { who: 'caller', at: 5, stage: 'greeting', ref: 'open', conf: 0.88, text: 'Hey, I just got rear-ended on Colfax.' },
      { who: 'line', at: 9, stage: 'consent', text: 'I\'m sorry, that\'s a scary thing. This call is recorded so we get your claim right. Is that okay?' },
      { who: 'caller', at: 17, stage: 'consent', ref: 'consent', text: 'Yeah, go ahead and record it.' },
      { who: 'line', at: 21, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
      { who: 'caller', at: 28, stage: 'identity', ref: 'policy', text: 'Policy number is LM-CO-311592.' },
      { who: 'line', at: 36, stage: 'identity', text: 'And the ZIP code on the policy, to check it\'s you?' },
      { who: 'caller', at: 41, stage: 'identity', ref: 'zip', text: 'Zip code is 80206.' },
      { who: 'line', at: 47, stage: 'safety', text: 'Found you, Kiara. Before anything else: are you safe, and is anyone hurt?' },
      { who: 'caller', at: 55, stage: 'safety', ref: 'hurt', conf: 0.84, text: 'My neck is a little sore but I\'m okay. Nobody else is hurt.' },
      { who: 'line', at: 65, stage: 'loss_type', text: 'I\'m sorry about your neck. If it gets worse, please see a doctor or call 911. Where and when did it happen?' },
      { who: 'caller', at: 78, stage: 'loss_type', ref: 'where', text: 'About twenty minutes ago, at Colfax and Josephine, I was stopped at the light.' },
      { who: 'line', at: 89, stage: 'loss_details', ref: 'ask', text: 'Thank you. Can you tell me about the other vehicle?' },
      { who: 'caller', at: 96, end: 107, stage: 'loss_details', ref: 'other', conf: 0.81, text: 'A pickup hit me from behind. The other driver gave me his insurance, it\'s with Front Range Auto.' },
    ])
    const call = callDetail(c, {
      n: L.n, startedAt, endedAt: null, state: 'with_line', language: 'en', callerLabel: 'Kiara Booker', region: 'US-CO',
      place: 'Colfax Ave, Denver', lossType: 'collision', outcome: 'in_progress', stage: stage('loss_details'),
      consentTurn: talk.t('consent'), policyNo: L.policyNo, policyNumber: L.policy, lineLabel: 'Line 2',
      flags: [flag('distress', 'Sounds shaken', 'Said her neck is sore; speaking slower than at the start.', 'warning', c.plus(startedAt, 55), talk.t('hurt'))],
    })
    const file = claimFile(L.callId, null, 'collision', 'Collision', [
      section('policy', 'Policy verified', [
        slot('policy_number', 'Policy', 'LM-CO-311592 · Kiara Booker', heard(talk, 'policy', 'LM-CO-311592')),
        slot('identity_check', 'Identity', 'Passed · ZIP code matches', lookedUp()),
        slot('insured_item', 'Car', '2020 Mazda3 · Auto Plus', fromPolicy()),
      ]),
      section('safety', 'People and safety', [
        slot('injury_reported', 'Anyone hurt', 'Sore neck', heard(talk, 'hurt', 'My neck is a little sore'), { value: true, conf: 0.9 }),
        slot('injury_detail', 'Others', 'Nobody else hurt', heard(talk, 'hurt', 'Nobody else is hurt.')),
      ]),
      section('loss', 'What happened', [
        slot('loss_type', 'Cause', 'Collision, rear-ended', heard(talk, 'open', 'I just got rear-ended on Colfax'), { value: 'collision' }),
        slot('loss_place', 'Where', 'Colfax Ave at Josephine St', heard(talk, 'where', 'at Colfax and Josephine')),
        slot('loss_time', 'When', 'Thu 8 Jan, about 7:20 a.m.', heard(talk, 'where', 'About twenty minutes ago'), { conf: 0.78 }),
      ]),
      section('details', 'The other vehicle', [
        slot('other_party_involved', 'Other vehicle', 'A pickup, hit her from behind', heard(talk, 'other', 'A pickup hit me from behind'), { value: true }),
        slot('other_party_insurer', 'Their insurer', 'Front Range Auto', heard(talk, 'other', 'it\'s with Front Range Auto'), { conf: 0.66 }),
        slot('police_report_filed', 'Police report', '', notYet()),
        slot('vehicle_drivable', 'Car can be driven', '', notYet()),
      ]),
      section('photos', 'Photos', [slot('photos_promised', 'Link', '', notYet('Next step'))]),
      section('coverage', 'Coverage basics', [
        slot('coverage_lines_mentioned', 'Covered', 'Collision and medical payments under Auto Plus', fromPolicy()),
        slot('deductible_mentioned', 'Deductible', '$500 collision', fromPolicy()),
      ]),
    ])
    out.calls[L.callId] = call
    out.transcripts[L.callId] = transcript(talk)
    out.claimFiles[L.callId] = file
    out.messages[L.callId] = []
    out.timelines[L.callId] = timelineFrom(talk, startedAt, c, [
      { atMs: 17800, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
      { atMs: 30500, kind: 'tool', label: 'Policy found in 0.3 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } },
      { atMs: 57000, kind: 'flag', label: 'Possible injury heard: sore neck', actor: 'ClaimVoice', data: { kind: 'distress' } },
    ])
    const line = liveLine(call, 'US-CO', 'collision', {
      mood: { key: 'shaken', label: 'Sounds shaken', detail: 'speaking slower' },
      heard: [
        { key: 'policy', text: 'Policy LM-CO-311592 ✓', tone: 'normal' },
        { key: 'neck', text: 'Sore neck', tone: 'caution' },
        { key: 'where', text: 'Colfax and Josephine', tone: 'normal' },
        { key: 'other', text: 'Other vehicle: a pickup', tone: 'normal' },
      ],
      lastAsked: { text: 'Can you tell me about the other vehicle?', textEn: null },
      claimFileProgress: file.progress,
      callerVerified: true,
      callerPhoneMasked: '•••-•••-0187',
    })
    out.liveLines[L.callId] = line
    out.lines.push(line)
  }

  // ------------------------------------------------------------ Line 3 · Martine Gagnon · Rosemont, Montréal · in French
  {
    const L = LIVE.martine
    const startedAt = c.iso(-365)
    const talk = new Talk(L.callId, L.n, 'fr', 'Martine Gagnon', [
      {
        who: 'line', at: 0, stage: 'consent',
        text: 'Bonjour, ici ClaimVoice, l\'assistant automatisé des réclamations de Larkspur Mutual. L\'appel est enregistré pour bien traiter votre réclamation. Est-ce que ça vous convient?',
        en: 'Hello, this is ClaimVoice, Larkspur Mutual\'s automated claims assistant. The call is recorded so we handle your claim properly. Is that all right?',
      },
      { who: 'caller', at: 9, stage: 'consent', ref: 'consent', text: 'Oui, j\'accepte. Un tuyau a éclaté pis mon sous-sol est inondé.', en: 'Yes, I agree. A pipe burst and my basement is flooded.' },
      { who: 'line', at: 15, stage: 'identity', text: 'Je suis désolée, on va s\'en occuper. Quel est votre numéro de police?', en: 'I\'m sorry, we\'ll take care of it. What\'s your policy number?' },
      { who: 'caller', at: 22, stage: 'identity', ref: 'policy', text: 'Mon numéro de police, c\'est LM-QC-118407.', en: 'My policy number is LM-QC-118407.' },
      {
        who: 'line', at: 52, stage: 'safety',
        text: 'Je vous ai trouvée, madame Gagnon. Est-ce que tout le monde est en sécurité, et est-ce que l\'eau s\'approche du panneau électrique?',
        en: 'Found you, Mrs Gagnon. Is everyone safe, and is the water anywhere near the electrical panel?',
      },
      { who: 'caller', at: 58, stage: 'safety', ref: 'safe', text: 'Personne n\'est blessé. Le panneau électrique est en haut, l\'eau ne s\'en approche pas.', en: 'Nobody is hurt. The electrical panel is upstairs; the water isn\'t near it.' },
      { who: 'line', at: 74, stage: 'loss_type', text: 'Tant mieux. Racontez-moi ce qui s\'est passé.', en: 'Good. Tell me what happened.' },
      { who: 'caller', at: 82, stage: 'loss_type', ref: 'story', text: 'Je l\'ai vu ce matin vers six heures. Avec le grand froid, un tuyau a gelé pis il a éclaté.', en: 'I saw it this morning around six. With the deep cold, a pipe froze and burst.' },
      { who: 'line', at: 100, stage: 'loss_details', text: 'C\'est stressant, je comprends. Combien d\'eau y a-t-il, et dans quelles pièces?', en: 'That\'s stressful, I understand. How much water is there, and in which rooms?' },
      {
        who: 'caller', at: 108, end: 132, stage: 'loss_details', ref: 'water',
        text: 'Il y a peut-être dix centimètres d\'eau dans la salle familiale pis la buanderie. J\'ai fermé l\'entrée d\'eau principale, l\'eau n\'entre plus.',
        en: 'There\'s maybe ten centimetres of water in the family room and the laundry room. I shut off the main water; it\'s not coming in any more.',
      },
      {
        who: 'line', at: 245, stage: 'loss_details',
        text: 'Une entreprise de nettoyage après sinistre peut passer aujourd\'hui. Voulez-vous que l\'expert vous en propose une?',
        en: 'A water clean-up company can come today. Would you like the adjuster to suggest one?',
      },
      { who: 'caller', at: 260, stage: 'loss_details', ref: 'cleanup', text: 'Oui, s\'il vous plaît, le plus vite possible. Le tapis est fini.', en: 'Yes please, as soon as possible. The carpet is ruined.' },
      {
        who: 'line', at: 348, stage: 'photos', ref: 'photo',
        text: 'Je vous envoie un lien par texto pour des photos du sous-sol et du tuyau. Gardez le morceau de tuyau, s\'il vous plaît.',
        en: 'I\'m texting you a link for photos of the basement and the pipe. Please keep the piece of pipe.',
      },
      { who: 'caller', at: 361, end: 364, stage: 'photos', ref: 'plumber', interrupted: true, text: 'Parfait. Est-ce que je peux appeler un plombier tout de suite, ou…', en: 'Perfect. Can I call a plumber right away, or…' },
    ])
    const call = callDetail(c, {
      n: L.n, startedAt, endedAt: null, state: 'with_line', language: 'fr', callerLabel: 'Martine Gagnon', region: 'CA-QC',
      place: 'Rosemont, Montréal', lossType: 'water', outcome: 'in_progress', stage: stage('photos'),
      consentTurn: talk.t('consent'), policyNo: L.policyNo, policyNumber: L.policy, lineLabel: 'Line 3',
      listeners: [{ userId: P.renee.id, name: P.renee.name, mode: 'listening' }],
    })
    const file = claimFile(L.callId, null, 'water', 'Water', [
      section('caller', 'Language', [
        slot('preferred_language', 'Service in', 'French, chosen by the caller', lookedUp('kept in French, English shown for staff'), { value: 'fr' }),
      ]),
      section('policy', 'Policy verified', [
        slot('policy_number', 'Policy', 'LM-QC-118407 · Martine Gagnon', heard(talk, 'policy', 'LM-QC-118407')),
        slot('identity_check', 'Identity', 'Passed · calling from the number on the policy', lookedUp()),
        slot('insured_item', 'Home', '4127 rue De Lanaudière, Montréal · Home Comprehensive', fromPolicy()),
      ]),
      section('loss', 'What happened', [
        slot('loss_type', 'Cause', 'Tuyau gelé, éclaté (frozen pipe, burst)', heard(talk, 'story', 'un tuyau a gelé pis il a éclaté'), { value: 'water' }),
        slot('loss_date', 'When', 'Ce matin, vers 6 h (this morning, about 6 a.m.)', heard(talk, 'story', 'ce matin vers six heures')),
      ]),
      section('details', 'Damage', [
        slot('water_depth', 'Water', 'Environ 10 cm (about 10 cm)', heard(talk, 'water', 'dix centimètres d\'eau'), { conf: 0.82 }),
        slot('rooms_affected', 'Rooms', 'Salle familiale, buanderie (family room, laundry room)', heard(talk, 'water', 'la salle familiale pis la buanderie')),
        slot('water_still_entering', 'Water stopped', 'Eau principale fermée (main water shut off)', heard(talk, 'water', 'J\'ai fermé l\'entrée d\'eau principale'), { value: false }),
        slot('mitigation_taken', 'Clean-up', 'Nettoyage voulu aujourd\'hui (clean-up wanted today)', heard(talk, 'cleanup', 'le plus vite possible')),
      ]),
      section('safety', 'Safety', [
        slot('injury_reported', 'Anyone hurt', 'Personne (nobody)', heard(talk, 'safe', 'Personne n\'est blessé'), { value: false }),
        slot('danger_now', 'Power', 'Panneau en haut, au sec (panel upstairs, dry)', heard(talk, 'safe', 'Le panneau électrique est en haut'), { value: false }),
      ]),
      section('photos', 'Photos', [
        slot('photo_link_sent_to', 'Link', 'Sent by text to •••-•••-0163', heard(talk, 'photo', 'Je vous envoie un lien par texto')),
        slot('photos_promised', 'Photos', '', notYet('Waiting for photos')),
      ]),
      section('coverage', 'Coverage basics', [
        slot('coverage_lines_mentioned', 'Burst pipe', 'Covered under Home Comprehensive', fromPolicy()),
        slot('deductible_mentioned', 'Deductible', '$1,000 home', fromPolicy()),
      ]),
    ])
    out.calls[L.callId] = call
    out.transcripts[L.callId] = transcript(talk)
    out.claimFiles[L.callId] = file
    out.messages[L.callId] = [{
      id: uid('sms', 3),
      toMasked: '•••-•••-0163',
      body: 'Larkspur Mutual : envoyez vos photos du sous-sol et du tuyau ici : /p/demo-photos-martine (lien valide 72 heures).',
      sentAt: c.plus(startedAt, 350),
      status: 'sent',
    }]
    out.timelines[L.callId] = timelineFrom(talk, startedAt, c, [
      { atMs: 9800, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
      { atMs: 24600, kind: 'tool', label: 'Policy found in 0.2 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } },
      { atMs: 245000, kind: 'listen', label: 'Renée Kowalchuk started listening', actor: P.renee.name, data: {} },
      { atMs: 350000, kind: 'photo_link', label: 'Photo link texted to •••-•••-0163', actor: 'ClaimVoice', data: { token: 'demo-photos-martine' } },
    ])
    const line = liveLine(call, 'CA-QC', 'water', {
      mood: { key: 'unsettled', label: 'Sounds worried', detail: null },
      heard: [
        { key: 'cause', text: 'Tuyau gelé, éclaté', tone: 'normal' },
        { key: 'water', text: 'Environ 10 cm d\'eau', tone: 'normal' },
        { key: 'main', text: 'Eau principale fermée', tone: 'normal' },
      ],
      lastAsked: {
        text: 'Je vous envoie un lien par texto pour des photos du sous-sol et du tuyau.',
        textEn: 'I\'m texting you a link for photos of the basement and the pipe.',
      },
      claimFileProgress: file.progress,
      callerVerified: true,
      callerPhoneMasked: '•••-•••-0163',
    })
    out.liveLines[L.callId] = line
    out.lines.push(line)
  }

  // ------------------------------------------------------------ Line 4 · Hal Petrenko · Airdrie · urgent safety
  {
    const L = LIVE.hal
    const startedAt = c.iso(-54)
    const talk = new Talk(L.callId, L.n, 'en', 'Hal Petrenko', [
      { who: 'line', at: 0, stage: 'consent', text: GREETING },
      { who: 'caller', at: 5, stage: 'consent', ref: 'gas', flags: ['urgent_safety'], text: 'Yeah, okay. Listen, the wind ripped the cover off my gas meter and I can smell gas by the side door.' },
      {
        who: 'line', at: 14, stage: 'safety', ref: 'leave',
        text: 'Please leave the house now with everyone inside. Don\'t use light switches or anything that sparks, and call 911 from outside. I\'ll stay on the line and get a person for you.',
      },
      { who: 'caller', at: 30, stage: 'safety', ref: 'outside', text: 'Okay. We\'re out, me and my wife and the dog. I called 911 from the driveway. [wind gusting]' },
      { who: 'line', at: 42, end: 50, stage: 'handoff', text: 'You did exactly right. Stay well away from the house. A person from Larkspur is joining you now.' },
    ])
    const requestedAt = c.iso(-38)
    const handoff: HandoffInfo = {
      id: uid('handoff', 4),
      callId: L.callId,
      reason: 'urgent_safety',
      reasonLabel: 'Urgent safety',
      detail: 'Smells gas after the wind tore the cover off his gas meter.',
      priority: 'urgent',
      state: 'waiting',
      requestedAt,
      waitingSeconds: 38,
      acceptedBy: null,
      acceptedAt: null,
      callerLabel: 'Hal Petrenko',
      lineLabel: 'Line 4',
      place: 'Airdrie',
      lossTypeLabel: 'Wind',
      language: 'en',
      summary: 'Hal smells gas by his side door after the wind tore the cover off his gas meter in Airdrie.\nHe is outside with his wife and dog, has called 911, and is still on the line.',
      actionsTaken: [
        'Told him to leave the house and call 911',
        'Told him not to use switches or anything that sparks',
        'Stayed on the line while he got outside',
      ],
      to: null,
      team: 'intake',
    }
    const call = callDetail(c, {
      n: L.n, startedAt, endedAt: null, state: 'waiting_for_person', language: 'en', callerLabel: 'Hal Petrenko', region: 'CA-AB',
      place: 'Airdrie', lossType: 'wind', outcome: 'in_progress', stage: stage('handoff'), consentTurn: talk.t('gas'),
      policyNo: L.policyNo, policyNumber: L.policy, surgeId: SURGE_ID, lineLabel: 'Line 4', handoff,
      summary: 'Smells gas after the wind tore the cover off his gas meter. Outside, has called 911, still on the line.',
      flags: [
        flag('urgent_safety', 'Urgent safety', 'Smells gas after the wind tore the cover off his gas meter.', 'critical', c.plus(startedAt, 5), talk.t('gas')),
        surgeFlag(startedAt),
      ],
    })
    const file = claimFile(L.callId, null, 'wind', 'Wind', [
      section('policy', 'Policy', [
        slot('policy_number', 'Policy', 'LM-AB-338420 · Hal Petrenko', lookedUp('matched by phone'), { confirmed: false }),
        slot('identity_check', 'Identity', '', notYet('Skipped for safety')),
      ]),
      section('safety', 'People and safety', [
        slot('danger_now', 'Danger', 'Smells gas; meter cover torn off', heard(talk, 'gas', 'I can smell gas by the side door'), { value: true }),
        slot('emergency_services_called', '911', 'Called from the driveway', heard(talk, 'outside', 'I called 911 from the driveway'), { value: true }),
        slot('injury_detail', 'Who is out', 'Him, his wife and the dog', heard(talk, 'outside', 'me and my wife and the dog')),
      ]),
      section('loss', 'What happened', [
        slot('loss_type', 'Cause', 'Wind', heard(talk, 'gas', 'the wind ripped the cover off my gas meter'), { value: 'wind' }),
        slot('loss_place', 'Where', 'At home, Airdrie', fromPolicy()),
      ]),
    ])
    out.calls[L.callId] = call
    out.transcripts[L.callId] = transcript(talk)
    out.claimFiles[L.callId] = file
    out.messages[L.callId] = []
    out.timelines[L.callId] = timelineFrom(talk, startedAt, c, [
      { atMs: 7000, kind: 'flag', label: 'Urgent safety: smell of gas', actor: 'ClaimVoice', data: { kind: 'urgent_safety' } },
      { atMs: 16000, kind: 'handoff', label: 'Waiting for a person (urgent)', actor: 'ClaimVoice', data: { reason: 'urgent_safety' } },
    ])
    out.liveLines[L.callId] = liveLine(call, 'CA-AB', 'wind', {
      mood: { key: 'shaken', label: 'Sounds shaken', detail: 'outside, waiting' },
      heard: [
        { key: 'gas', text: 'Smells gas', tone: 'caution' },
        { key: '911', text: 'Called 911', tone: 'normal' },
        { key: 'out', text: 'Everyone outside', tone: 'normal' },
      ],
      lastAsked: null,
      claimFileProgress: file.progress,
      callerVerified: false,
      callerPhoneMasked: '•••-•••-0119',
    })
    out.handoffTray.push(handoff)
  }

  // ------------------------------------------------------------ Line 5 · Wendy Arsenault · Bridgeland, Calgary · asked for a person
  {
    const L = LIVE.wendy
    const startedAt = c.iso(-152)
    const talk = new Talk(L.callId, L.n, 'en', 'Wendy Arsenault', [
      { who: 'line', at: 0, stage: 'consent', text: GREETING },
      { who: 'caller', at: 6, stage: 'consent', ref: 'consent', text: 'Yes, that\'s fine.' },
      { who: 'line', at: 9, stage: 'safety', text: 'Thank you. I\'ve found a policy for the number you\'re calling from, Wendy. Before anything else: is everyone safe, and is anything dangerous right now?' },
      {
        who: 'caller', at: 20, end: 38, stage: 'safety', ref: 'fence',
        text: 'We\'re fine. But the wind knocked my whole back fence onto my neighbour\'s car and he\'s pretty upset. Can I talk to a person, please? I want to get this right.',
      },
      { who: 'line', at: 40, end: 50, stage: 'handoff', text: 'Of course. I\'m bringing in a person now and passing on what you\'ve told me, so you won\'t have to repeat it. The wait is about a minute.' },
    ])
    const handoff: HandoffInfo = {
      id: uid('handoff', 5),
      callId: L.callId,
      reason: 'caller_asked',
      reasonLabel: 'Asked for a person',
      detail: 'The wind knocked her back fence onto her neighbour\'s car. She wants to talk it through with a person.',
      priority: 'normal',
      state: 'waiting',
      requestedAt: c.iso(-112),
      waitingSeconds: 112,
      acceptedBy: null,
      acceptedAt: null,
      callerLabel: 'Wendy Arsenault',
      lineLabel: 'Line 5',
      place: 'Bridgeland, Calgary',
      lossTypeLabel: 'Wind',
      language: 'en',
      summary: 'The wind knocked Wendy\'s back fence onto her neighbour\'s car in Bridgeland overnight; nobody is hurt.\nHer neighbour is upset and she wants a person to explain what happens next.',
      actionsTaken: [
        'Found her policy from the number she called from',
        'Checked that nobody is hurt',
        'Told her the wait is about a minute',
      ],
      to: null,
      team: 'intake',
    }
    const call = callDetail(c, {
      n: L.n, startedAt, endedAt: null, state: 'waiting_for_person', language: 'en', callerLabel: 'Wendy Arsenault', region: 'CA-AB',
      place: 'Bridgeland, Calgary', lossType: 'wind', outcome: 'in_progress', stage: stage('handoff'), consentTurn: talk.t('consent'),
      policyNo: L.policyNo, policyNumber: L.policy, surgeId: SURGE_ID, lineLabel: 'Line 5', handoff,
      summary: 'Fence blown onto the neighbour\'s car. Asked for a person.',
      flags: [surgeFlag(startedAt)],
    })
    const file = claimFile(L.callId, null, 'wind', 'Wind', [
      section('policy', 'Policy', [
        slot('policy_number', 'Policy', 'LM-AB-291076 · Wendy Arsenault', lookedUp('matched by phone')),
      ]),
      section('safety', 'People and safety', [
        slot('injury_reported', 'Anyone hurt', 'No', heard(talk, 'fence', 'We\'re fine.'), { value: false }),
      ]),
      section('details', 'Damage', [
        slot('siding_or_fence_damage', 'Fence', 'Back fence down', heard(talk, 'fence', 'the wind knocked my whole back fence'), { value: true }),
        slot('neighbour_property_damaged', 'Neighbour\'s property', 'Fence fell on the neighbour\'s car', heard(talk, 'fence', 'onto my neighbour\'s car'), { value: true }),
      ]),
    ])
    out.calls[L.callId] = call
    out.transcripts[L.callId] = transcript(talk)
    out.claimFiles[L.callId] = file
    out.messages[L.callId] = []
    out.timelines[L.callId] = timelineFrom(talk, startedAt, c, [
      { atMs: 6500, kind: 'consent', label: 'Caller agreed to recording', actor: 'ClaimVoice', data: { answer: 'given' } },
      { atMs: 8200, kind: 'tool', label: 'Policy found in 0.2 s', actor: 'ClaimVoice', data: { tool: 'find_policy', ok: true } },
      { atMs: 40000, kind: 'handoff', label: 'Asked for a person: waiting', actor: 'ClaimVoice', data: { reason: 'caller_asked' } },
    ])
    out.liveLines[L.callId] = liveLine(call, 'CA-AB', 'wind', {
      mood: { key: 'unsettled', label: 'Sounds unsettled', detail: null },
      heard: [
        { key: 'fence', text: 'Back fence down', tone: 'normal' },
        { key: 'car', text: 'On the neighbour\'s car', tone: 'normal' },
        { key: 'hurt', text: 'Nobody hurt', tone: 'normal' },
      ],
      lastAsked: null,
      claimFileProgress: file.progress,
      callerVerified: true,
      callerPhoneMasked: '•••-•••-0154',
    })
    out.handoffTray.push(handoff)
  }

  return out
}

function buildSurge(c: Clock): Surge {
  return {
    id: SURGE_ID,
    kind: 'wind',
    kindLabel: 'Wind',
    title: SURGE_TITLE,
    region: 'CA-AB',
    regionLabel: 'Alberta',
    areaLabel: 'Calgary and Airdrie',
    startedAt: c.atIso(-1, '20:00'),
    endedAt: null,
    active: true,
    headline: 'Gusts over 100 km/h overnight: roofs, fences and siding',
    source: 'Environment and Climate Change Canada wind warning (bundled snapshot)',
    callsLastHour: 17,
    usualCallsPerHour: 5,
    multiplier: 3.4,
    sinceLabel: 'since 6 a.m.',
    surgeQuestionsOn: true,
    waitForPersonSeconds: 60,
    standbyAvailable: 2,
    standbyCalled: false,
    policiesInArea: 96,
    claimsSoFar: 3,
    guidance: 'Wind damage to roofs, siding and skylights is covered under Home Comprehensive; fences up to $5,000.',
  }
}

