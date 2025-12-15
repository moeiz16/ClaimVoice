// Reference data (GET /meta) and Settings: scripts, consent rules, hand-off rules, languages, retention, privacy.
import type { ConsentRule, HandoffRules, Languages, Meta, Privacy, Retention, Role, Script, ScriptQuestion } from '~/types/api'
import { type Clock, P, ref, STAGE_KEYS, type Who } from './kit'
import { ROLE_LABEL } from './people'

export const LOSS_TYPES = [
  { key: 'collision', label: 'Collision', line: 'auto' },
  { key: 'hail', label: 'Hail', line: 'property' },
  { key: 'wind', label: 'Wind', line: 'property' },
  { key: 'water', label: 'Water', line: 'property' },
  { key: 'fire', label: 'Fire or smoke', line: 'property' },
  { key: 'theft', label: 'Theft or break-in', line: 'auto' },
] as const
export type LossKey = typeof LOSS_TYPES[number]['key']
export const LOSS_LABEL: Record<LossKey, string> = {
  collision: 'Collision', hail: 'Hail', wind: 'Wind', water: 'Water', fire: 'Fire or smoke', theft: 'Theft or break-in',
}

export const REGIONS = [
  { code: 'CA-AB', label: 'Alberta', country: 'CA', consentRule: 'one_party' },
  { code: 'CA-QC', label: 'Québec', country: 'CA', consentRule: 'one_party' },
  { code: 'US-CO', label: 'Colorado', country: 'US', consentRule: 'one_party' },
  { code: 'US-CA', label: 'California', country: 'US', consentRule: 'all_party' },
  { code: 'US-WA', label: 'Washington', country: 'US', consentRule: 'all_party' },
  { code: 'US-FL', label: 'Florida', country: 'US', consentRule: 'all_party' },
] as const
export type RegionCode = typeof REGIONS[number]['code']
export const REGION_LABEL: Record<RegionCode, string> = {
  'CA-AB': 'Alberta', 'CA-QC': 'Québec', 'US-CO': 'Colorado', 'US-CA': 'California', 'US-WA': 'Washington', 'US-FL': 'Florida',
}

const ROLE_ORDER: Role[] = ['admin', 'supervisor', 'intake_agent', 'adjuster', 'siu_investigator', 'compliance']

export function buildMeta(): Meta {
  return {
    product: 'ClaimVoice',
    version: '1.0.0',
    languages: [{ key: 'en', label: 'English' }, { key: 'fr', label: 'Français' }],
    lossTypes: LOSS_TYPES.map(l => ({ key: l.key, label: l.label, line: l.line })),
    regions: REGIONS.map(r => ({ code: r.code, label: r.label, country: r.country, consentRule: r.consentRule })),
    stages: STAGE_KEYS,
    routes: [
      { key: 'fast_track', label: 'Fast-track' },
      { key: 'adjuster', label: 'Adjuster' },
      { key: 'special_investigation', label: 'Closer look' },
    ],
    roles: ROLE_ORDER.map(r => ({ key: r, label: ROLE_LABEL[r] })),
    demoScenarios: [
      { key: 'calgary-windstorm', label: 'Chinook wind damage to a home, Calgary' },
      { key: 'denver-rear-end', label: 'Rear-ended at a red light, Denver' },
      { key: 'montreal-basement', label: 'Basement flooded by a burst pipe, Montréal (in French)' },
    ],
  }
}

// ---------------------------------------------------------------- scripts

interface QOpts { required?: boolean, when?: string | null, choices?: string[], surgeOnly?: boolean }
function q(slotKey: string, label: string, kind: string, en: string, fr: string, o: QOpts = {}): ScriptQuestion {
  return { slotKey, label, kind, prompt: { en, fr }, required: o.required ?? true, when: o.when ?? null, choices: o.choices ?? [], surgeOnly: o.surgeOnly ?? false }
}

const WHEN_DATE = q('loss_date', 'When it happened', 'date', 'When did it happen?', 'Quand est-ce arrivé?')
const WHEN_TIME = q('loss_time', 'About what time', 'time', 'About what time was that?', 'Vers quelle heure?')
const PLACE_HOME = q('loss_place', 'Where', 'address', 'Is this at the home on your policy?', 'Est-ce à l\'adresse inscrite à votre police?')
const LIVABLE = q('home_livable', 'Home livable', 'yes_no', 'Can you stay in the home tonight?', 'Pouvez-vous rester dans la maison ce soir?')
const PHOTOS = q('photos_promised', 'Photos', 'yes_no', 'Can I text you a link to send photos when it\'s light and safe?', 'Puis-je vous envoyer un lien par texto pour des photos, quand ce sera sécuritaire?')

interface ScriptSpec { lossType: LossKey, line: 'auto' | 'property', version: number, by: Who, day: number, time: string, questions: ScriptQuestion[] }

function scriptSpecs(): ScriptSpec[] {
  return [
    {
      lossType: 'collision', line: 'auto', version: 6, by: P.renee, day: -21, time: '10:12',
      questions: [
        q('loss_place', 'Where', 'text', 'Where did it happen? A street and the nearest cross street is fine.', 'Où est-ce arrivé? Une rue et l\'intersection la plus proche suffisent.'),
        WHEN_DATE, WHEN_TIME,
        q('other_party_involved', 'Another vehicle', 'yes_no', 'Was another vehicle involved?', 'Un autre véhicule était-il impliqué?'),
        q('other_party_insurer', 'Other driver\'s insurer', 'text', 'Did you get the other driver\'s insurance details?', 'Avez-vous obtenu les coordonnées d\'assurance de l\'autre conducteur?', { when: 'other_party_involved == true' }),
        q('police_report_filed', 'Police report', 'yes_no', 'Did the police attend, or have you filed a report?', 'La police est-elle venue, ou avez-vous fait un rapport?'),
        q('vehicle_drivable', 'Car can be driven', 'yes_no', 'Can your car be driven safely?', 'Votre véhicule peut-il rouler en toute sécurité?'),
        q('damage_areas', 'Damage', 'choice', 'Where is the damage on your car?', 'Où sont les dommages sur votre véhicule?', { choices: ['Front', 'Rear', 'Driver side', 'Passenger side', 'Roof', 'Glass'] }),
        PHOTOS,
      ],
    },
    {
      lossType: 'hail', line: 'property', version: 3, by: P.nadia, day: -30, time: '14:40',
      questions: [
        PLACE_HOME, WHEN_DATE, WHEN_TIME,
        q('roof_or_window_damage', 'Roof or windows', 'yes_no', 'Is the roof, a window or a skylight damaged?', 'Le toit, une fenêtre ou un puits de lumière sont-ils endommagés?'),
        q('water_still_entering', 'Water coming in', 'yes_no', 'Is any water coming inside right now?', 'De l\'eau entre-t-elle à l\'intérieur en ce moment?'),
        q('damage_areas', 'Vehicles', 'text', 'Was a vehicle outside during the hail?', 'Un véhicule était-il dehors pendant la grêle?', { required: false }),
        PHOTOS,
      ],
    },
    {
      lossType: 'wind', line: 'property', version: 4, by: P.nadia, day: -3, time: '11:05',
      questions: [
        PLACE_HOME, WHEN_DATE, WHEN_TIME,
        q('roof_or_window_damage', 'Roof, windows or skylights', 'yes_no', 'Is the roof, a window or a skylight damaged?', 'Le toit, une fenêtre ou un puits de lumière sont-ils endommagés?'),
        q('siding_or_fence_damage', 'Siding or fence', 'yes_no', 'Is any siding or fencing damaged?', 'Le revêtement extérieur ou une clôture sont-ils endommagés?'),
        q('mitigation_taken', 'Covered up', 'yes_no', 'Is anything open to the weather, or have you been able to cover it?', 'Y a-t-il une ouverture aux intempéries, ou avez-vous pu la couvrir?'),
        LIVABLE,
        q('debris_source', 'Where the debris came from', 'text', 'Did anything blow in from somewhere else, like a neighbour\'s fence, deck or tree?', 'Quelque chose a-t-il été projeté d\'ailleurs, comme la clôture, la terrasse ou un arbre d\'un voisin?', { surgeOnly: true, required: false }),
        q('neighbour_property_damaged', 'Neighbour\'s property', 'yes_no', 'Did anything from your property land on a neighbour\'s home or car?', 'Quelque chose de chez vous est-il tombé sur la maison ou la voiture d\'un voisin?', { surgeOnly: true, required: false }),
      ],
    },
    {
      lossType: 'water', line: 'property', version: 5, by: P.renee, day: -24, time: '9:30',
      questions: [
        q('water_source', 'Where the water came from', 'choice', 'Where is the water coming from?', 'D\'où vient l\'eau?', { choices: ['Burst or frozen pipe', 'Appliance', 'Sewer backup', 'Surface water', 'Roof'] }),
        q('water_still_entering', 'Water still coming in', 'yes_no', 'Is water still coming in?', 'L\'eau entre-t-elle encore?'),
        q('mitigation_taken', 'Water shut off', 'yes_no', 'Have you been able to shut off the main water valve?', 'Avez-vous pu fermer l\'entrée d\'eau principale?', { when: 'water_source == "Burst or frozen pipe"' }),
        q('rooms_affected', 'Rooms', 'text', 'Which rooms are affected?', 'Quelles pièces sont touchées?'),
        WHEN_DATE,
        LIVABLE,
        PHOTOS,
      ],
    },
    {
      lossType: 'fire', line: 'property', version: 2, by: P.nadia, day: -34, time: '15:20',
      questions: [
        q('emergency_services_called', 'Fire department', 'yes_no', 'Has the fire department been called?', 'Avez-vous appelé les pompiers?'),
        q('loss_description', 'What burned', 'text', 'Where did the fire or smoke start?', 'Où le feu ou la fumée ont-ils commencé?'),
        q('rooms_affected', 'Rooms', 'text', 'Which rooms have fire or smoke damage?', 'Quelles pièces ont des dommages de feu ou de fumée?'),
        WHEN_DATE,
        LIVABLE,
        q('temporary_lodging_needed', 'Somewhere to stay', 'yes_no', 'Do you need somewhere to stay tonight?', 'Avez-vous besoin d\'un endroit où dormir ce soir?', { when: 'home_livable == false' }),
      ],
    },
    {
      lossType: 'theft', line: 'auto', version: 3, by: P.renee, day: -19, time: '16:45',
      questions: [
        q('loss_description', 'What was taken', 'text', 'What was taken?', 'Qu\'est-ce qui a été volé?'),
        q('loss_place', 'Where', 'text', 'Where was it taken from?', 'D\'où a-t-il été volé?'),
        WHEN_DATE,
        q('police_report_filed', 'Police report', 'yes_no', 'Have you reported it to the police?', 'L\'avez-vous signalé à la police?'),
        q('police_report_number', 'Report number', 'text', 'Do you have the report number?', 'Avez-vous le numéro du rapport?', { when: 'police_report_filed == true', required: false }),
        q('damage_areas', 'Damage from the break-in', 'text', 'Was anything damaged getting in, like a window or a lock?', 'Quelque chose a-t-il été brisé pour entrer, comme une vitre ou une serrure?', { required: false }),
        PHOTOS,
      ],
    },
  ]
}

export function buildScripts(c: Clock): Script[] {
  return scriptSpecs().map(s => ({
    lossType: s.lossType,
    lossTypeLabel: LOSS_LABEL[s.lossType],
    line: s.line,
    version: s.version,
    questions: s.questions,
    updatedAt: c.atIso(s.day, s.time),
    updatedBy: ref(s.by),
  }))
}

// ---------------------------------------------------------------- consent

const ANNOUNCE_ONE = {
  en: 'This call is recorded so we get your claim right. Is that okay?',
  fr: 'L\'appel est enregistré pour bien traiter votre réclamation. Est-ce que ça vous convient?',
}
const ANNOUNCE_ALL = {
  en: 'Before we start: this call is recorded so we get your claim right, and nothing is kept unless you say yes. Is that okay?',
  fr: 'Avant de commencer : l\'appel est enregistré pour bien traiter votre réclamation, et rien n\'est conservé sans votre accord. Est-ce que ça vous convient?',
}
const ON_REFUSAL_ONE = 'Recording stops; notes only; a person is offered'
const ON_REFUSAL_ALL = 'Nothing is kept; notes only from the caller\'s answers; a person is offered'

export function buildConsentRules(): ConsentRule[] {
  const rule = (region: RegionCode, all: boolean, basis: string): ConsentRule => ({
    region,
    regionLabel: REGION_LABEL[region],
    rule: all ? 'all_party' : 'one_party',
    ruleLabel: `${all ? 'All-party' : 'One-party'} consent (${REGION_LABEL[region]})`,
    announcement: all ? ANNOUNCE_ALL : ANNOUNCE_ONE,
    basis,
    onRefusal: all ? ON_REFUSAL_ALL : ON_REFUSAL_ONE,
    isDefault: true,
  })
  return [
    rule('CA-AB', false, 'Criminal Code of Canada, s. 184; PIPEDA and Alberta PIPA notice'),
    rule('CA-QC', false, 'Criminal Code of Canada, s. 184; Québec Law 25 notice, given in French first'),
    rule('US-CO', false, 'Colorado Revised Statutes §18-9-303'),
    rule('US-CA', true, 'California Penal Code §632'),
    rule('US-WA', true, 'Revised Code of Washington §9.73.030'),
    rule('US-FL', true, 'Florida Statutes §934.03'),
  ]
}

export function buildHandoffRules(): HandoffRules {
  return {
    urgentKeywords: ['gas', 'smoke', 'fire', 'someone hurt', 'trapped', 'water near the panel', 'power line down'],
    askedTimes: 1,
    lowConfidenceTurns: 2,
    distressThreshold: 0.7,
    identityAttempts: 3,
    offerPersonOnConsentRefusal: true,
    maxWaitSeconds: 90,
    urgentSafetyAlways: true,
  }
}

export function buildLanguages(): Languages {
  return {
    enabled: ['en', 'fr'],
    voices: { en: { voice: 'Clara (en-CA)', speed: 1 }, fr: { voice: 'Amélie (fr-CA)', speed: 1 } },
    default: 'en',
    detectAutomatically: true,
    frenchFirstRegions: ['CA-QC'],
  }
}

export function buildRetention(c: Clock): Retention {
  return {
    recordingsYears: 7,
    transcriptsYears: 7,
    photosYears: 7,
    claimFilesYears: 7,
    cardNumberMoments: 'always_removed',
    refusedConsentTranscripts: 'not_kept',
    deletionRequestsWaiting: 2,
    lastPurgeAt: c.atIso(-7, '3:00'),
    nextPurgeOn: '2026-02-01',
  }
}

export function buildPrivacy(): Privacy {
  return { privacyOfficerName: P.priya.name, privacyOfficerEmail: 'priya.sandhu@larkspurmutual.ca', privacyNoticeUrl: null }
}
