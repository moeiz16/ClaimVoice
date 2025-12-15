// The claims screenshots lean on: CV-26-01856 (Tomás Reyes, the closer-look claim Lena re-routed), CV-26-01842 (Dana
// Whitcombe, the landing page's recorded call) and CV-26-01851 (Arjun Bains, the late hand-off).
import type { SlotHistory } from '~/types/api'
import {
  buildClaim, type ClaimBuild, type ClaimSpec, claimCallId, claimCallNo, dayLabel, GREETING_EN,
} from './claimkit'
import { flag } from './calls'
import {
  CARD, type Clock, editedBy, fromPolicy, heard, type Line, lookedUp, moment, P, section, slot, Talk, TZ,
} from './kit'

// ---------------------------------------------------------------- CV-26-01856 · Tomás Reyes · Denver · rear-ended

export function buildTomas(c: Clock): ClaimBuild {
  const n = 2
  const policyStart = c.date(-20, TZ.denver) // 19 days before the loss on Wed 7 Jan
  const coverageRaised = c.date(-16, TZ.denver)
  const lines: Line[] = [
    { who: 'line', at: 0, end: 7.5, stage: 'consent', ref: 'greet', text: GREETING_EN },
    { who: 'caller', at: 8, end: 10, stage: 'consent', ref: 'consent', text: 'Yeah, that\'s fine.' },
    { who: 'line', at: 11, end: 17, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', at: 24, end: 34, stage: 'identity', ref: 'policy', text: 'Hang on, it\'s on the card. It\'s LM-CO-604181.' },
    { who: 'line', at: 40, end: 45, stage: 'safety', ref: 'found', text: 'Found it, Tomás. Before anything else: is everyone safe right now?' },
    { who: 'caller', at: 47, end: 51, stage: 'safety', ref: 'safe', text: 'Yeah, I\'m home. It happened last night.' },
    { who: 'line', at: 53, end: 56, stage: 'loss_type', text: 'I\'m glad you\'re home. Tell me what happened.' },
    { who: 'caller', at: 58, end: 80, stage: 'loss_type', ref: 'story', text: 'I was stopped at a red light on Speer Boulevard at I-25 and a car rear-ended me. It was 5:52, I checked my dash cam.' },
    { who: 'line', at: 84, end: 96, stage: 'loss_details', text: 'That sounds jarring. Is your car the 2022 Honda Civic on your policy, and did you exchange details with the other driver?' },
    { who: 'caller', at: 108, end: 128, stage: 'loss_details', ref: 'card', text: `That's the one. Yeah, he gave me his insurance card. Do you need my card too, for the deductible? It's ${CARD}` },
    { who: 'line', at: 129, end: 139, stage: 'loss_details', ref: 'stop', text: 'Please stop there. I never take card numbers on this line, and that part of the recording is removed. Can you describe the other car?' },
    { who: 'caller', at: 141, end: 148, stage: 'loss_details', ref: 'camry', text: 'A grey Toyota Camry, an older one.' },
    { who: 'line', at: 150, end: 156, stage: 'loss_details', text: 'Thank you. Where is your car now, and can it be driven?' },
    { who: 'caller', at: 158, end: 165, stage: 'loss_details', ref: 'towed', text: 'It\'s at Front Range Towing. The trunk won\'t close, so no.' },
    { who: 'line', at: 168, end: 171, stage: 'safety', text: 'Are you hurt at all?' },
    { who: 'caller', at: 172, end: 180, stage: 'safety', ref: 'neck', text: 'My neck\'s stiff. I\'m seeing a doctor this afternoon. Nobody else was in the car.' },
    { who: 'line', at: 182, end: 190, stage: 'loss_details', ref: 'confirm_ask', text: 'I\'m sorry, I hope it eases. Just to confirm, the other vehicle was a grey Camry?' },
    { who: 'caller', at: 192, end: 199, stage: 'loss_details', ref: 'suv', conf: 0.86, text: 'Uh, it was a silver SUV, I think. A RAV4 maybe.' },
    { who: 'line', at: 204, end: 213, stage: 'loss_details', ref: 'police_ask', text: 'Thanks, I\'ve noted both. An adjuster will confirm the details with you. Did the police come to the scene?' },
    { who: 'caller', at: 214, end: 221, stage: 'loss_details', ref: 'police', text: 'Yeah, an officer came. He gave me a card with a case number, I don\'t have it on me.' },
    { who: 'caller', at: 222, end: 228, stage: 'loss_details', ref: 'pressure', label: 'Another voice on the call', conf: 0.74, text: 'Ask them how fast they pay out. We need the money this week.' },
    { who: 'line', at: 230, end: 242, stage: 'coverage', ref: 'no_promise', text: 'I hear someone else there. An adjuster decides on payment after they review the claim, so I can\'t give a date, but they\'ll call you today.' },
    { who: 'caller', at: 244, end: 252, stage: 'coverage', ref: 'rental', text: 'That\'s my cousin, sorry. Can I get a rental today? I need it for work.' },
    { who: 'line', at: 254, end: 264, stage: 'coverage', ref: 'coverage', text: 'Your policy includes a rental car while yours is being repaired, up to $40 a day, and the adjuster will set it up. Your collision deductible is $500.' },
    { who: 'line', at: 268, end: 276, stage: 'photos', ref: 'photo', text: 'I\'m texting you a link for photos of the damage and the other driver\'s insurance card.' },
    { who: 'caller', at: 278, end: 281, stage: 'photos', ref: 'got', text: 'Got it, it just came in.' },
    {
      who: 'line', at: 284, end: 326, stage: 'read_back', ref: 'readback',
      text: 'Here\'s what I have: you were rear-ended at a red light on Speer Boulevard at I-25 on Wednesday at 5:52 p.m. Your 2022 Honda Civic\'s trunk won\'t close and it\'s at Front Range Towing. Your neck is stiff and you\'re seeing a doctor today. The other car was described as a grey Camry and as a silver SUV, and an officer gave you a case number. Is that right?',
    },
    { who: 'caller', at: 328, end: 331, stage: 'read_back', ref: 'yes', text: 'Yeah, that\'s right.' },
    { who: 'line', at: 334, end: 356, stage: 'wrap_up', ref: 'close', text: 'Your claim number is CV-26-01856. An adjuster, Lena Ortiz, will call you by noon today about the rental and your car. Please have the officer\'s case number handy. Take care of that neck.' },
    { who: 'caller', at: 358, end: 360, stage: 'wrap_up', text: 'Thanks. Bye.' },
    { who: 'line', at: 362, end: 383, stage: 'wrap_up', text: 'Thanks for calling Larkspur Mutual, Tomás. If anything changes, call this number any time, day or night. Goodbye.' },
  ]
  const talk = new Talk(claimCallId(n), claimCallNo(n), 'en', 'Tomás Reyes', lines)
  const callStart = c.atIso(0, '6:40:36', TZ.denver)
  const at = (s: number) => c.plus(callStart, s)
  const overrideAt = c.atIso(0, '7:26', TZ.denver)

  const camry: SlotHistory = { value: 'Grey Toyota Camry', display: 'Grey Toyota Camry', source: 'heard', changedBy: null, at: at(141), span: talk.span('camry', 'A grey Toyota Camry'), note: null }
  const suv: SlotHistory = { value: 'Silver SUV, maybe a RAV4', display: 'Silver SUV, maybe a RAV4', source: 'heard', changedBy: null, at: at(192), span: talk.span('suv', 'a silver SUV, I think. A RAV4 maybe.'), note: 'Caller changed his description when asked to confirm.' }

  const sections = [
    section('caller', 'Caller', [
      slot('caller_name', 'Caller', 'Tomás Reyes, policyholder', fromPolicy()),
      slot('callback_number', 'Call back on', '•••-•••-0458', fromPolicy()),
    ]),
    section('policy', 'Policy', [
      slot('policy_number', 'Policy', 'LM-CO-604181 ✓', heard(talk, 'policy', 'LM-CO-604181')),
      slot('policy_start', 'Started', dayLabel(policyStart), fromPolicy(), { required: false }),
      slot('identity_check', 'Identity', 'Passed · calling from the number on the policy', lookedUp()),
      slot('insured_item', 'His car', '2022 Honda Civic · Auto Plus', fromPolicy()),
    ]),
    section('loss', 'Collision', [
      slot('loss_place', 'Where', 'Speer Blvd at I-25, Denver', heard(talk, 'story', 'Speer Boulevard at I-25')),
      slot('loss_date', 'When', 'Wed 7 Jan, 5:52 p.m.', heard(talk, 'story', 'It was 5:52'), { value: `${c.date(-1, TZ.denver)}T17:52` }),
      slot('loss_description', 'What happened', 'Rear-ended while stopped at a red light', heard(talk, 'story', 'a car rear-ended me')),
    ]),
    section('details', 'The cars', [
      slot('vehicle_drivable', 'His car', 'Trunk won\'t close, not drivable', heard(talk, 'towed', 'The trunk won\'t close'), { value: false }),
      slot('vehicle_location', 'Where it is', 'Front Range Towing', heard(talk, 'towed', 'It\'s at Front Range Towing'), { required: false }),
      slot('other_party_vehicle', 'Other car', 'Silver Toyota RAV4 (police report)', editedBy(P.lena), {
        changedAt: 192,
        history: [camry, suv, { value: 'Silver Toyota RAV4', display: 'Silver Toyota RAV4 (police report)', source: 'person', changedBy: P.lena.name, at: overrideAt, span: null, note: 'Police report confirms the SUV.' }],
      }),
      slot('other_party_insurer', 'Their insurer', 'On the card he was given (photo)', heard(talk, 'card', 'he gave me his insurance card')),
      slot('police_report_filed', 'Police', 'Officer came to the scene', heard(talk, 'police', 'an officer came'), { value: true }),
      slot('police_report_number', 'Report number', 'DPD 26-003871', editedBy(P.lena), { required: false }),
    ]),
    section('safety', 'People', [
      slot('injury_reported', 'Injury', 'Stiff neck, doctor today', heard(talk, 'neck', 'My neck\'s stiff'), { value: true }),
      slot('injury_detail', 'Passengers', 'None', heard(talk, 'neck', 'Nobody else was in the car.')),
      slot('third_party_on_call', 'Also on the call', 'His cousin, asked how fast we pay', heard(talk, 'pressure', 'Ask them how fast they pay out'), { required: false, conf: 0.74 }),
    ]),
    section('photos', 'Photos', [
      slot('photos_promised', 'Photos', '3 received at 7:10 a.m.', lookedUp('from the text link')),
    ]),
    section('coverage', 'Coverage basics', [
      slot('coverage_lines_mentioned', 'Rental', 'Up to $40 a day while his car is repaired', heard(talk, 'coverage', 'up to $40 a day')),
      slot('deductible_mentioned', 'Deductible', '$500 collision', heard(talk, 'coverage', 'Your collision deductible is $500')),
    ]),
  ]

  const spec: ClaimSpec = {
    n,
    number: 'CV-26-01856',
    holder: 'Tomás Reyes',
    lang: 'en',
    region: 'US-CO',
    place: 'Speer Blvd at I-25, Denver',
    line: 'auto',
    lossType: 'collision',
    lossDay: -1,
    policyNumber: 'LM-CO-604181',
    status: 'in_review',
    assignee: P.lena,
    end: [0, '6:47:00'],
    duration: 384,
    description: 'Rear-ended at a red light on Speer Blvd at I-25 on Wed 7 Jan at 5:52 p.m. Trunk won\'t close; car at Front Range Towing. Stiff neck, seeing a doctor today. Asked for a rental.',
    short: 'Tomás was rear-ended at a red light on Speer Boulevard at I-25 on Wednesday evening. His 2022 Honda Civic\'s trunk won\'t close and it is at Front Range Towing. His neck is stiff; he is seeing a doctor today. He asked for a rental car.',
    links: [
      ['rear-ended at a red light', 'story'],
      ['trunk won\'t close', 'towed'],
      ['neck is stiff', 'neck'],
      ['asked for a rental car', 'rental'],
    ],
    checked: { by: P.lena, at: c.atIso(0, '7:28', TZ.denver) },
    nextSteps: [
      'Lena Ortiz calls Tomás by noon about the rental and his car',
      'Rental car up to $40 a day while the Civic is repaired',
      'Dev Malhotra reviews the three signs alongside the claim',
      'Tomás sends the officer\'s case number',
    ],
    photos: [['car_rear', 'Rear bumper'], ['car_rear', 'Trunk lid'], ['card', 'Other driver\'s insurance card']],
    photosAfter: 23,
    hushes: [[118, 128]],
    moments: t => [
      moment('consent', 'Consent', t, 'consent'),
      moment('policy', 'Policy', t, 'found'),
      moment('safety', 'Card number stopped', t, 'card', 118),
      moment('sign', 'Other car changed', t, 'suv'),
      moment('photos', 'Photo link', t, 'photo'),
      moment('read_back', 'Read-back', t, 'readback'),
    ],
    sms: {
      token: 'photos-cv-26-01856',
      to: '•••-•••-0458',
      turn: 'photo',
      body: 'Larkspur Mutual: send photos of the damage and the other driver\'s insurance card here: /p/photos-cv-26-01856 (link works for 72 hours).',
    },
    timelineExtras: [
      { atMs: 199000, kind: 'flag', label: 'Description of the other car changed', actor: 'ClaimVoice', data: { kind: 'siu_signal' } },
      { atMs: 228000, kind: 'notice', label: 'Second voice on the call asked about payment speed', actor: 'ClaimVoice', data: {} },
    ],
    routing: {
      route: 'adjuster',
      model: 'special_investigation',
      size: [0.46, 'moderate', 4000, 9000],
      look: [0.19, 'elevated'],
      reasons: [
        ['vehicle_drivable', 'Car can\'t be driven, rear damage', 'raises', 0.34, 'towed'],
        ['injury_reported', 'Possible neck injury', 'raises', 0.29, 'neck'],
        ['rental_needed', 'Rental car needed today', 'raises', 0.12, 'rental'],
      ],
      signs: [
        { key: 'new_policy', label: 'Policy started 19 days before the loss', evidence: `Policy started ${dayLabel(policyStart)}; collision on ${dayLabel(c.date(-1, TZ.denver))}.`, source: 'policy', weight: 0.31 },
        { key: 'coverage_raised', label: 'Coverage raised last month', evidence: `Rental cover added and the collision deductible lowered on ${dayLabel(coverageRaised)}.`, source: 'policy', weight: 0.24 },
        { key: 'third_party_pressure', label: 'A third party pushed for a fast payment on the call', evidence: '“Ask them how fast they pay out. We need the money this week.”', source: 'call', turn: 'pressure', weight: 0.22 },
      ],
      rules: ['A possible injury is never fast-tracked', 'A closer look needs a high score and at least 2 signs: both were present'],
      override: { reason: 'Police report confirms the SUV.', by: P.lena, at: overrideAt },
      siu: { status: 'open' },
    },
    flags: (t, startedAt) => [
      flag('distress', 'Possible injury', 'Stiff neck; seeing a doctor today.', 'warning', c.plus(startedAt, 172), t.t('neck')),
      flag('siu_signal', 'Signs worth a closer look', '3 of the 14 signs we check', 'warning', c.plus(startedAt, 404)),
    ],
  }
  return buildClaim(c, spec, talk, sections)
}

// ---------------------------------------------------------------- CV-26-01842 · Dana Whitcombe · Calgary · skylight

export function buildDana(c: Clock): ClaimBuild {
  const n = 5
  const lines: Line[] = [
    { who: 'line', at: 0, end: 5.4, stage: 'consent', ref: 'greet', text: GREETING_EN },
    { who: 'caller', at: 5.8, end: 7.0, stage: 'consent', ref: 'consent', text: 'Yes, that\'s fine.' },
    { who: 'line', at: 7.3, end: 10.2, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', at: 10.6, end: 14.6, stage: 'identity', ref: 'policy', text: 'It\'s L-M, A-B, one-two-oh, five-nine-four.' },
    { who: 'line', at: 15.0, end: 17.4, stage: 'safety', ref: 'safety', text: 'Found it, Dana. Is everyone safe right now?' },
    { who: 'caller', at: 17.8, end: 23.6, stage: 'safety', ref: 'story', text: 'Yes, we\'re fine. A board off the neighbour\'s deck just came through the skylight over the kitchen. [wind gusting] The wind is unreal.' },
    { who: 'line', at: 24.0, end: 27.2, stage: 'loss_details', ref: 'open_ask', text: 'I\'m sorry, that sounds frightening. Is wind or snow coming in through the skylight?' },
    { who: 'caller', at: 27.6, end: 31.6, stage: 'loss_details', ref: 'cover', text: 'A bit of snow. I\'ve taped a garbage bag and a piece of plywood over the hole.' },
    { who: 'line', at: 32.0, end: 34.2, stage: 'loss_details', text: 'That\'s exactly right. When did it happen?' },
    { who: 'caller', at: 34.6, end: 37.6, stage: 'loss_details', ref: 'when', text: 'About ten past two. Just a few minutes ago.' },
    { who: 'line', at: 38.0, end: 40.8, stage: 'loss_details', text: 'Was anything else damaged, like the roof or the car?' },
    { who: 'caller', at: 41.2, end: 46.6, stage: 'loss_details', ref: 'card', text: `I don't think so. Do you need my card for the deductible? It's ${CARD}` },
    { who: 'line', at: 46.8, end: 52.0, stage: 'loss_details', ref: 'stop', text: 'Please stop there. I never take card numbers on this line, and that part of the recording is removed.' },
    { who: 'caller', at: 52.3, end: 53.4, stage: 'loss_details', text: 'Oh. Okay, good.' },
    { who: 'line', at: 53.8, end: 58.2, stage: 'photos', ref: 'photo', text: 'I\'m texting you a link for photos of the skylight. Take them when it\'s safe.' },
    { who: 'caller', at: 58.6, end: 59.4, stage: 'photos', text: 'Got it.' },
    { who: 'line', at: 59.8, end: 66.6, stage: 'read_back', ref: 'readback', text: 'Here\'s what I have: wind at 1418 Elbow Drive Southwest around 2:10, the kitchen skylight smashed by debris and covered for now, and nobody hurt. Is that right?' },
    { who: 'caller', at: 67.0, end: 67.9, stage: 'read_back', ref: 'yes', text: 'That\'s right.' },
    { who: 'line', at: 68.3, end: 75.6, stage: 'wrap_up', ref: 'close', text: 'Your claim number is CV-26-01842. Because of the storm, a repair company will call you by 10 a.m. to secure the skylight. Call back any time.' },
  ]
  const talk = new Talk(claimCallId(n), claimCallNo(n), 'en', 'Dana Whitcombe', lines)
  const sections = [
    section('policy', 'Policy verified', [
      slot('policy_number', 'Policy', 'LM-AB-120594 · Dana Whitcombe', heard(talk, 'policy', 'one-two-oh, five-nine-four')),
      slot('identity_check', 'Identity', 'Passed · calling from the number on the policy', lookedUp()),
      slot('insured_item', 'Home', '1418 Elbow Drive SW, Calgary · Home Comprehensive', fromPolicy()),
    ]),
    section('safety', 'People and safety', [
      slot('injury_reported', 'Anyone hurt', 'No', heard(talk, 'story', 'we\'re fine'), { value: false }),
    ]),
    section('loss', 'What happened', [
      slot('loss_type', 'Cause', 'Wind (Chinook)', heard(talk, 'story', 'The wind is unreal'), { value: 'wind' }),
      slot('loss_time', 'When', 'Thu 8 Jan, about 2:10 a.m.', heard(talk, 'when', 'About ten past two'), { value: '02:10' }),
      slot('loss_place', 'Where', '1418 Elbow Drive SW, Calgary', fromPolicy()),
    ]),
    section('details', 'Damage', [
      slot('roof_or_window_damage', 'Kitchen skylight', 'Smashed by blown debris', heard(talk, 'story', 'came through the skylight over the kitchen'), { value: true }),
      slot('debris_source', 'Debris from', 'A board off the neighbour\'s deck', heard(talk, 'story', 'A board off the neighbour\'s deck'), { required: false }),
      slot('water_still_entering', 'Weather coming in', 'A bit of snow, now covered', heard(talk, 'cover', 'A bit of snow'), { value: false }),
      slot('mitigation_taken', 'Covered up', 'Garbage bag and plywood over the hole', heard(talk, 'cover', 'I\'ve taped a garbage bag and a piece of plywood over the hole'), { value: true }),
      slot('other_damage', 'Anything else', 'Nothing she knows of', heard(talk, 'card', 'I don\'t think so'), { conf: 0.74, required: false }),
      slot('card_number_moment', 'Card numbers', 'She started one at 0:44. Not kept; 2 seconds cut.', lookedUp('removed'), { required: false }),
    ]),
    section('photos', 'Photos', [
      slot('photos_promised', 'Photos', '2 received at 2:31 a.m.', lookedUp('from the text link')),
    ]),
    section('coverage', 'Coverage basics', [
      slot('coverage_lines_mentioned', 'Wind', 'Covered: skylights under Home Comprehensive', fromPolicy()),
      slot('deductible_mentioned', 'Deductible', '$1,000 home', fromPolicy()),
    ]),
  ]
  const spec: ClaimSpec = {
    n,
    number: 'CV-26-01842',
    holder: 'Dana Whitcombe',
    lang: 'en',
    region: 'CA-AB',
    place: 'Elbow Park, Calgary',
    line: 'property',
    lossType: 'wind',
    lossDay: 0,
    policyNumber: 'LM-AB-120594',
    status: 'assigned',
    assignee: P.jamal,
    end: [0, '2:14:00'],
    duration: 76,
    surge: true,
    description: 'Chinook wind: a board off the neighbour\'s deck smashed the kitchen skylight at about 2:10 a.m. Covered with plywood; a little snow came in. Nobody hurt.',
    short: 'A board off the neighbour\'s deck came through Dana\'s kitchen skylight at about 2:10 a.m. during the Chinook. She covered the hole with plywood, so only a little snow got in. Nobody is hurt.',
    links: [
      ['came through Dana\'s kitchen skylight', 'story'],
      ['at about 2:10 a.m.', 'when'],
      ['covered the hole with plywood', 'cover'],
      ['Nobody is hurt', 'story'],
    ],
    checked: { by: P.jamal, at: c.atIso(0, '6:05') },
    nextSteps: [
      'A repair company calls Dana by 10 a.m. to secure the skylight',
      'Fast-track: the repair quote can be approved without an adjuster visit',
    ],
    photos: [['skylight', 'Kitchen skylight from below'], ['skylight', 'Plywood over the hole']],
    photosAfter: 17,
    hushes: [[44.6, 46.6]],
    moments: t => [
      moment('consent', 'Consent', t, 'consent'),
      moment('policy', 'Policy', t, 'safety'),
      moment('safety', 'Card number stopped', t, 'card', 44.6),
      moment('photos', 'Photo link', t, 'photo'),
      moment('read_back', 'Read-back', t, 'readback'),
      moment('claim_number', 'Claim number', t, 'close'),
    ],
    sms: {
      token: 'photos-cv-26-01842',
      to: '•••-•••-0193',
      turn: 'photo',
      body: 'Larkspur Mutual: send photos of the skylight here when it\'s safe: /p/photos-cv-26-01842 (link works for 72 hours).',
    },
    routing: {
      route: 'fast_track',
      size: [0.12, 'small', 1500, 4000],
      look: [0.02, 'low'],
      reasons: [
        ['weather_match', 'Wind warning confirmed for Calgary at 8 p.m.', 'lowers', 0.31, null],
        ['open_to_weather', 'Skylight covered, nothing open to the weather', 'lowers', 0.27, 'cover'],
        ['policy_tenure', 'Policy active 6 years, no open claims', 'lowers', 0.18, null],
      ],
      rules: ['A covered skylight is not open to the weather, so fast-track is allowed'],
    },
  }
  return buildClaim(c, spec, talk, sections)
}

// ---------------------------------------------------------------- CV-26-01851 · Arjun Bains · Calgary · late hand-off

export function buildArjun(c: Clock): ClaimBuild {
  const n = 4
  const lines: Line[] = [
    { who: 'line', at: 0, end: 7, stage: 'consent', text: GREETING_EN },
    { who: 'caller', at: 8, end: 9.4, stage: 'consent', ref: 'consent', text: 'Yeah, sure.' },
    { who: 'line', at: 10, end: 14, stage: 'identity', text: 'Thank you. What\'s your policy number, or the phone number on your policy?' },
    { who: 'caller', at: 16, end: 20, stage: 'identity', ref: 'policy', text: '403 555 0178.' },
    { who: 'line', at: 22, end: 30, stage: 'safety', ref: 'safety', text: 'Found it, Arjun. Before anything else: is everyone safe, and is anything leaking, sparking or smelling of gas?' },
    { who: 'caller', at: 32, end: 35, stage: 'safety', ref: 'safe', text: 'We\'re all okay. No gas or anything.' },
    { who: 'line', at: 37, end: 39, stage: 'loss_type', text: 'Good. Tell me what happened.' },
    { who: 'caller', at: 41, end: 58, stage: 'loss_type', ref: 'story', text: 'The wind took a big strip of shingles off the back of the roof, and the siding\'s hanging off the garage wall. I can see the plywood up there.' },
    { who: 'line', at: 60, end: 66, stage: 'loss_details', text: 'I\'m sorry, that\'s a lot to wake up to. Is any water or snow getting inside?' },
    { who: 'caller', at: 68, end: 74, stage: 'loss_details', ref: 'wet', text: 'There\'s a wet patch on the ceiling in the back bedroom.' },
    { who: 'line', at: 76, end: 83, stage: 'loss_details', text: 'Did any debris blow in from somewhere else, like a neighbour\'s fence or tree?' },
    { who: 'caller', at: 85, end: 87, stage: 'loss_details', ref: 'ours', text: 'No, it\'s all ours.' },
    { who: 'line', at: 90, end: 94, stage: 'loss_details', text: 'Thanks. When did you first notice the damage?' },
    { who: 'caller', at: 96, end: 101, stage: 'loss_details', ref: 'when', text: 'About five this morning. The noise woke us up.' },
    { who: 'line', at: 104, end: 112, stage: 'photos', ref: 'photo', text: 'I\'m texting you a link for photos of the roof and the garage wall. Take them when it\'s light and safe.' },
    { who: 'caller', at: 114, end: 115, stage: 'photos', text: 'Okay.' },
    { who: 'line', at: 120, end: 134, stage: 'coverage', ref: 'cover', text: 'Your Home Comprehensive policy covers wind damage to the roof and siding, with a $1,000 deductible. An adjuster decides what\'s paid after they look.' },
    { who: 'caller', at: 136, end: 139, stage: 'coverage', text: 'Right. And how long does that take?' },
    { who: 'line', at: 141, end: 148, stage: 'coverage', text: 'An adjuster will call you today to set up a visit. Is the wet patch on the ceiling getting bigger?' },
    { who: 'caller', at: 150, end: 156, stage: 'coverage', ref: 'plate', text: 'Not really. It\'s about the size of a dinner plate.' },
    { who: 'caller', at: 210, end: 218, stage: 'coverage', ref: 'ask_person', text: 'Look, can I just talk to someone? I need to know if I can get my own roofer out today.' },
    { who: 'line', at: 220, end: 228, stage: 'coverage', ref: 'kept_going', text: 'I can help with that. A repair company can tarp the roof today. Can I first check the address for the visit?' },
    { who: 'caller', at: 230, end: 236, stage: 'coverage', ref: 'again', text: 'It\'s on the policy. I\'d really like a person, please.' },
    { who: 'line', at: 238, end: 242, stage: 'handoff', ref: 'bring', text: 'Of course. I\'m bringing in a person now.' },
    { who: 'person', at: 250, end: 264, stage: 'handoff', ref: 'jamal', label: P.jamal.name, text: 'Hi Arjun, it\'s Jamal at Larkspur. I\'ve read what you told ClaimVoice. Yes, you can call your own roofer to tarp it today; keep the receipt and we\'ll cover it.' },
    { who: 'caller', at: 266, end: 270, stage: 'handoff', text: 'Great, that\'s all I needed. Thanks, Jamal.' },
    {
      who: 'person', at: 272, end: 298, stage: 'read_back', ref: 'readback', label: P.jamal.name,
      text: 'Here\'s what I have: the wind took shingles off the back of the roof and tore the siding off the garage wall around five this morning, there\'s a wet patch the size of a dinner plate on the back bedroom ceiling, and nobody is hurt. Is that right?',
    },
    { who: 'caller', at: 300, end: 302, stage: 'read_back', ref: 'yes', text: 'That\'s it.' },
    { who: 'person', at: 304, end: 318, stage: 'wrap_up', ref: 'close', label: P.jamal.name, text: 'Your claim number is CV-26-01851. An adjuster will call you today to book a visit. Send the roofer\'s receipt with your photos.' },
  ]
  const talk = new Talk(claimCallId(n), claimCallNo(n), 'en', 'Arjun Bains', lines)
  const sections = [
    section('policy', 'Policy verified', [
      slot('policy_number', 'Policy', 'LM-AB-150927 · Arjun Bains', lookedUp('found from the phone number')),
      slot('callback_number', 'Phone', '403 555 0178', heard(talk, 'policy', '403 555 0178')),
      slot('insured_item', 'Home', 'Martindale, Calgary · Home Comprehensive', fromPolicy()),
    ]),
    section('safety', 'People and safety', [
      slot('injury_reported', 'Anyone hurt', 'No', heard(talk, 'safe', 'We\'re all okay'), { value: false }),
      slot('danger_now', 'Gas, water, power', 'None', heard(talk, 'safe', 'No gas or anything.'), { value: false }),
    ]),
    section('loss', 'What happened', [
      slot('loss_type', 'Cause', 'Wind (Chinook)', heard(talk, 'story', 'The wind took a big strip of shingles'), { value: 'wind' }),
      slot('loss_time', 'When', 'Thu 8 Jan, about 5 a.m.', heard(talk, 'when', 'About five this morning')),
    ]),
    section('details', 'Damage', [
      slot('roof_or_window_damage', 'Roof', 'Strip of shingles gone at the back; plywood showing', heard(talk, 'story', 'I can see the plywood up there'), { value: true }),
      slot('siding_or_fence_damage', 'Siding', 'Hanging off the garage wall', heard(talk, 'story', 'the siding\'s hanging off the garage wall'), { value: true }),
      slot('water_still_entering', 'Water inside', 'Wet patch on the back bedroom ceiling, about dinner-plate size', heard(talk, 'wet', 'a wet patch on the ceiling in the back bedroom'), { value: true }),
      slot('debris_source', 'Debris from', 'None, all their own', heard(talk, 'ours', 'it\'s all ours'), { required: false }),
      slot('mitigation_taken', 'Covered up', 'His own roofer will tarp it today (keep the receipt)', heard(talk, 'jamal', 'you can call your own roofer to tarp it today')),
    ]),
    section('photos', 'Photos', [
      slot('photos_promised', 'Photos', 'Link sent, none yet', lookedUp('from the text link'), { required: false }),
    ]),
    section('coverage', 'Coverage basics', [
      slot('coverage_lines_mentioned', 'Wind', 'Roof and siding under Home Comprehensive', heard(talk, 'cover', 'covers wind damage to the roof and siding')),
      slot('deductible_mentioned', 'Deductible', '$1,000 home', heard(talk, 'cover', 'a $1,000 deductible')),
    ]),
  ]
  const callStart = c.atIso(0, '6:14:30')
  const spec: ClaimSpec = {
    n,
    number: 'CV-26-01851',
    holder: 'Arjun Bains',
    lang: 'en',
    region: 'CA-AB',
    place: 'Martindale, Calgary',
    line: 'property',
    lossType: 'wind',
    lossDay: 0,
    policyNumber: 'LM-AB-150927',
    status: 'new',
    assignee: null,
    end: [0, '6:21:00'],
    duration: 390,
    surge: true,
    lineLabel: 'Line 2',
    description: 'Chinook wind tore shingles off the back of the roof and the siding off the garage wall at about 5 a.m. Plywood showing; wet patch on a bedroom ceiling. His own roofer will tarp it today.',
    short: 'The wind took a strip of shingles off the back of Arjun\'s roof and tore the siding off his garage wall at about 5 a.m. There is a wet patch on the back bedroom ceiling. Jamal told him his own roofer can tarp it today.',
    links: [
      ['took a strip of shingles off the back of Arjun\'s roof', 'story'],
      ['wet patch on the back bedroom ceiling', 'wet'],
      ['his own roofer can tarp it today', 'jamal'],
    ],
    checked: { by: P.jamal, at: c.atIso(0, '6:24') },
    nextSteps: ['An adjuster calls Arjun today to book a visit', 'Arjun sends the roofer\'s receipt with his photos'],
    photos: [],
    sms: { token: 'photos-cv-26-01851', to: '•••-•••-0178', turn: 'photo', body: 'Larkspur Mutual: send photos of the roof and the garage wall here when it\'s light and safe: /p/photos-cv-26-01851' },
    moments: t => [
      moment('consent', 'Consent', t, 'consent'),
      moment('policy', 'Policy', t, 'safety'),
      moment('photos', 'Photo link', t, 'photo'),
      moment('handoff', 'Asked for a person', t, 'ask_person'),
      moment('handoff', 'Jamal joined', t, 'jamal'),
      moment('read_back', 'Read-back', t, 'readback'),
      moment('claim_number', 'Claim number', t, 'close'),
    ],
    timelineExtras: [
      { atMs: 238000, kind: 'handoff', label: 'Asked for a person: waiting', actor: 'ClaimVoice', data: { reason: 'caller_asked' } },
      { atMs: 248000, kind: 'handoff', label: 'Jamal Haddad took the call', actor: P.jamal.name, data: { state: 'accepted' } },
    ],
    flags: () => [flag('surge', 'In the surge', 'Chinook windstorm, Calgary', 'info', callStart)],
    routing: {
      route: 'adjuster',
      size: [0.58, 'moderate', 8000, 18000],
      look: [0.03, 'low'],
      reasons: [
        ['open_to_weather', 'Roof open to the weather: plywood showing', 'raises', 0.36, 'story'],
        ['water_inside', 'Water stain on a bedroom ceiling', 'raises', 0.24, 'wet'],
        ['siding_damage', 'Siding torn off a wall', 'raises', 0.14, 'story'],
      ],
      rules: ['A roof open to the weather goes to an adjuster'],
    },
  }
  return buildClaim(c, spec, talk, sections)
}

