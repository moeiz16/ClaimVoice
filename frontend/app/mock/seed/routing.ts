// Routing checks (docs/API_CONTRACT.md §1.10): the size check and the closer-look check, the four questions a
// regulator asks, fact sheets in plain words with a technical fold, and fairness tables.
import type {
  Check, CheckKey, CheckVersion, Dot, FactSection, FactSheet, Fairness, FairnessRow, GateResult, MetricSet, Question,
  RoutingChecks, SignOff, WeekColumn,
} from '~/types/api'
import { type Clock, P, ref, type Who } from './kit'

const NEVER = [
  'denies a claim',
  'uses age, gender, language or postcode to route',
  'stops a person changing the route',
  'changes version without two sign-offs',
]
const FAIRNESS_NOTE = 'Age, language and region are never used to route a claim. We use them only here, to check fairness.'
const SPLIT = 'Time split: trained on losses before 1 Oct 2025, tested on Oct to Dec 2025'
const ALGORITHM = 'Boosted decision trees with calibration'
const TRAINED_ON = '4,812 practice claim calls with losses from Jan 2023 to Sep 2025'

function signed(side: SignOff['side'], by: Who, at: string, note: string | null = null): SignOff {
  return { side, sideLabel: side === 'claims' ? 'Claims' : 'Model risk', by: ref(by), at, note, state: 'signed' }
}
function waiting(side: SignOff['side'], by: Who): SignOff {
  return { side, sideLabel: side === 'claims' ? 'Claims' : 'Model risk', by: ref(by), at: null, note: null, state: 'waiting' }
}

function gates(m: MetricSet, baseline: MetricSet, fairGap: number, fastGap: number, stability: number, psi: number): GateResult[] {
  const g = (key: string, label: string, value: number, limit: number, higherIsBetter: boolean): GateResult =>
    ({ key, label, value: Math.round(value * 1000) / 1000, limit, passed: higherIsBetter ? value >= limit : value <= limit })
  return [
    g('beats_baseline', 'Clearly better than the simple baseline', m.prAuc - baseline.prAuc, 0.02, true),
    g('calibration', 'When it says 7 in 10, about 7 in 10 happen', m.ece, 0.05, false),
    g('fair_closer_look', 'Closer-look rate within 1.5 points for every group', fairGap, 0.015, false),
    g('fair_fast_track', 'Fast-track rate within 5 points for every group', fastGap, 0.05, false),
    g('reasons_stable', 'Top reasons stay the same when retrained', stability, 0.7, true),
    g('calls_like_training', 'Recent calls look like the ones it learned from', psi, 0.25, false),
  ]
}

const SIZE_TEST: MetricSet = { auc: 0.86, prAuc: 0.71, brier: 0.081, ece: 0.021, recallAtThreshold: 0.91, precisionAtThreshold: 0.58, threshold: 0.32 }
const SIZE_BASE: MetricSet = { auc: 0.81, prAuc: 0.63, brier: 0.094, ece: 0.034, recallAtThreshold: 0.9, precisionAtThreshold: 0.49, threshold: 0.29 }
const SIZE_RF: MetricSet = { auc: 0.84, prAuc: 0.68, brier: 0.086, ece: 0.029 }
const LOOK_TEST: MetricSet = { auc: 0.83, prAuc: 0.34, brier: 0.031, ece: 0.018, recallAtThreshold: 0.62, precisionAtThreshold: 0.41, threshold: 0.18 }
const LOOK_V5: MetricSet = { auc: 0.85, prAuc: 0.37, brier: 0.03, ece: 0.016, recallAtThreshold: 0.65, precisionAtThreshold: 0.43, threshold: 0.17 }
const LOOK_BASE: MetricSet = { auc: 0.77, prAuc: 0.26, brier: 0.035, ece: 0.027, recallAtThreshold: 0.55, precisionAtThreshold: 0.3, threshold: 0.15 }
const LOOK_RF: MetricSet = { auc: 0.81, prAuc: 0.31, brier: 0.033, ece: 0.022 }

/** A smooth curve through (0,0) and (1,1) bowed by `k` (bigger = better), 11 points. */
function curve(k: number): { x: number, y: number }[] {
  return Array.from({ length: 11 }, (_, i) => {
    const x = i / 10
    return { x, y: Math.round((1 - (1 - x) ** k) * 1000) / 1000 }
  })
}
/** Precision falling from `top` to the base rate as recall rises, 11 points. */
function prCurve(top: number, base: number): { x: number, y: number }[] {
  return Array.from({ length: 11 }, (_, i) => {
    const x = i / 10
    return { x, y: Math.round((base + (top - base) * (1 - x ** 1.6)) * 1000) / 1000 }
  })
}
function calibration(counts: number[], wobble: number[]): { predicted: number, observed: number, count: number }[] {
  return counts.map((count, i) => {
    const predicted = Math.round((0.05 + i * 0.1) * 100) / 100
    return { predicted, observed: Math.round((predicted + (wobble[i] ?? 0)) * 1000) / 1000, count }
  })
}

// ---------------------------------------------------------------- fairness

interface Group { dimension: Dot['dimension'], group: string, label: string, count: number }
const GROUPS: Group[] = [
  { dimension: 'region', group: 'CA-AB', label: 'Alberta', count: 1180 },
  { dimension: 'region', group: 'US-CO', label: 'Colorado', count: 640 },
  { dimension: 'region', group: 'CA-QC', label: 'Québec', count: 320 },
  { dimension: 'language', group: 'en', label: 'English', count: 1790 },
  { dimension: 'language', group: 'fr', label: 'French', count: 350 },
  { dimension: 'age_band', group: 'under_30', label: 'Under 30', count: 410 },
  { dimension: 'age_band', group: '30_64', label: '30 to 64', count: 1330 },
  { dimension: 'age_band', group: '65_plus', label: '65 and over', count: 400 },
]
const LOOK_RATES = [0.043, 0.039, 0.038, 0.042, 0.037, 0.047, 0.040, 0.036]
const FAST_RATES = [0.59, 0.57, 0.56, 0.585, 0.565, 0.6, 0.578, 0.571]

function fairnessRows(rates: number[], overall: number, band: number, tprBase: number, fprBase: number): FairnessRow[] {
  return GROUPS.map((g, i) => {
    const rate = rates[i] ?? overall
    const gap = Math.round((rate - overall) * 1000) / 1000
    return {
      dimension: g.dimension,
      group: g.group,
      label: g.label,
      count: g.count,
      flaggedRate: rate,
      truePositiveRate: Math.round((tprBase + gap * 2) * 1000) / 1000,
      falsePositiveRate: Math.round((fprBase + gap / 2) * 1000) / 1000,
      gap,
      withinBand: Math.abs(gap) <= band,
    }
  })
}

// ---------------------------------------------------------------- build

export interface RoutingSeed {
  routingChecks: RoutingChecks
  checks: Record<string, Check>
  factSheets: Record<string, FactSheet>
  fairness: Record<string, Fairness>
}

export function buildRouting(c: Clock): RoutingSeed {
  const inUseSince = c.date(-24) // 15 Dec 2025
  const v4Claims = c.atIso(-27, '15:10')
  const v4Risk = c.atIso(-25, '11:40')
  const v5Claims = c.atIso(-2, '9:40')

  const sizeV4: CheckVersion = {
    version: 4, stage: 'in_use', algorithm: ALGORITHM, inUseSince, trainedOn: TRAINED_ON, metrics: SIZE_TEST,
    gates: gates(SIZE_TEST, SIZE_BASE, 0.006, 0.021, 0.84, 0.09), gatesPassed: true,
    signOffs: [signed('claims', P.renee, v4Claims), signed('model_risk', P.priya, v4Risk)],
  }
  const lookV4: CheckVersion = {
    version: 4, stage: 'in_use', algorithm: ALGORITHM, inUseSince, trainedOn: TRAINED_ON, metrics: LOOK_TEST,
    gates: gates(LOOK_TEST, LOOK_BASE, 0.006, 0.021, 0.78, 0.145), gatesPassed: true,
    signOffs: [signed('claims', P.renee, v4Claims), signed('model_risk', P.priya, v4Risk)],
  }
  const lookV5: CheckVersion = {
    version: 5, stage: 'candidate', algorithm: ALGORITHM, inUseSince: null,
    trainedOn: '5,120 practice claim calls with losses from Jan 2023 to Sep 2025, with more theft and storm calls',
    metrics: LOOK_V5, gates: gates(LOOK_V5, LOOK_BASE, 0.005, 0.019, 0.81, 0.12), gatesPassed: true,
    signOffs: [signed('claims', P.renee, v5Claims, 'Trialled since 2 Jan on the closer-look queue; investigators agree as often as with version 4.'), waiting('model_risk', P.priya)],
  }

  const size: Check = {
    key: 'size', name: 'Size check', question: 'How big is this claim likely to be?', decides: 'Decides fast-track or adjuster.',
    inUse: sizeV4, candidate: null, status: 'healthy', statusLabel: 'Working as expected', signedBy: ref(P.priya),
  }
  const look: Check = {
    key: 'closer_look', name: 'Closer-look check', question: 'Should someone in special investigations look at it?',
    decides: 'Flags signs for a person in special investigations. Never denies a claim.',
    inUse: lookV4, candidate: lookV5, status: 'watch', statusLabel: 'Watch: storm week', signedBy: ref(P.priya),
  }

  const lookOverall = 0.041
  const lookBand = 0.015
  const dots: Dot[] = GROUPS.map((g, i) => {
    const rate = LOOK_RATES[i] ?? lookOverall
    return { dimension: g.dimension, group: g.group, label: g.label, rate, count: g.count, withinBand: Math.abs(rate - lookOverall) <= lookBand }
  })
  const weekLabels = ['17 Nov', '24 Nov', '1 Dec', '8 Dec', '15 Dec', '22 Dec', '29 Dec', '5 Jan']
  const weekPsi = [0.04, 0.05, 0.035, 0.055, 0.075, 0.065, 0.048, 0.145]

  const questions: Question[] = [
    {
      key: 'right',
      question: 'How often is it right?',
      answer: 'Of 1,240 claims sent to fast-track in December, **1,191 closed without needing an adjuster**.',
      foot: 'When it says “likely 7 in 10”, about 7 in 10 such claims turn out that way. Checked every month.',
      bars: [
        { label: 'Size check', value: 0.96, ours: true },
        { label: 'Old rule of thumb', value: 0.81, ours: false },
        { label: 'Closer look: investigators agreed', value: 0.7, ours: true },
        { label: 'Random spot checks', value: 0.4, ours: false },
      ],
    },
    {
      key: 'fair',
      question: 'Is it fair to everyone?',
      answer: 'Every group gets a closer look at **about the same rate**, inside the 1.5-point band we set.',
      foot: FAIRNESS_NOTE,
      dots,
      overallRate: lookOverall,
      band: lookBand,
    },
    {
      key: 'like_learned',
      question: 'Are this week\'s calls like the ones it learned from?',
      answer: 'Mostly. **More wind claims than usual**, which we expect during the storm.',
      foot: 'No action needed. If it reaches “Act”, fast-track pauses and every claim goes to an adjuster until someone reviews it.',
      weeks: weekLabels.map((label, i): WeekColumn => {
        const psi = weekPsi[i] ?? 0
        return { label, psi, status: psi >= 0.25 ? 'act' : psi >= 0.1 ? 'watch' : 'stable' }
      }),
    },
    {
      key: 'replace',
      question: 'Should version 5 replace version 4?',
      answer: 'Version 5 is **a little more accurate and just as fair**. It needs one more sign-off.',
      foot: 'A new version goes into use only when every check passes and two different people have signed it off.',
      compare: [
        { key: 'right', label: 'Right about which claims need a look', inUse: '96 in 100', candidate: '97 in 100', better: true },
        { key: 'investigators_agreed', label: 'Investigators agreed', inUse: '7 in 10', candidate: '7 in 10', better: null },
        { key: 'fair', label: 'Fair across groups', inUse: '✓ Inside the band', candidate: '✓ Inside the band', better: null },
        { key: 'reasons_same', label: 'Reasons stay the same', inUse: '✓ Stable', candidate: '✓ Stable', better: null },
      ],
      signOffs: lookV5.signOffs,
    },
  ]

  const routingChecks: RoutingChecks = {
    caption: 'Two checks run when a call ends. A person can change any route. Reviewed monthly; last review Mon 5 Jan.',
    checks: [size, look],
    questions,
    never: NEVER,
  }

  const sizeSections: FactSection[] = [
    { key: 'for', title: 'What it is for', body: ['Estimates how big and how involved a claim is likely to be, from what the caller told the line.', 'Small, simple claims go to fast-track; the rest go to an adjuster first.'] },
    { key: 'not_for', title: 'What it is not for', body: ['It never approves, denies or prices a claim.', 'It does not decide what is covered. The policy and an adjuster do.'] },
    { key: 'looks_at', title: 'What it looks at', body: ['What happened and to what: the loss type, the damage described, whether a home is open to the weather, whether a car can be driven.', 'The safety answers, a police report, photos, and the caller\'s own rough estimate.', 'How long the policy has been active and recent claims on it.'] },
    { key: 'never_looks_at', title: 'What it never looks at', body: ['Age, gender, language, region or postcode.', 'Names, date of birth, or anything about how a voice sounds: accent, pitch, stress or speed.'] },
    { key: 'tested', title: 'How it was tested', body: ['Learned from practice calls with losses before 1 October 2025, then tested on October to December 2025, so it never saw the answers.', 'Right 96 in 100 times on December fast-track claims, against 81 in 100 for the old rule of thumb.'] },
    { key: 'limits', title: 'Known limits', body: ['Storm weeks bring more of one kind of claim than it learned from. We watch for this every week.', 'When a caller is unsure what happened it has less to go on, so those claims lean towards an adjuster.'] },
    { key: 'fairness', title: 'Fairness', body: ['Fast-track rates by region, language and age band all sit within 5 points of the overall rate.', FAIRNESS_NOTE] },
    { key: 'sign_offs', title: 'Sign-offs', body: ['Version 4 was signed off for claims by Renée Kowalchuk and for model risk by Priya Sandhu, and has been in use since 15 Dec 2025.'] },
    { key: 'technical', title: 'For the technical reviewer', body: ['Boosted decision trees with calibration, compared with a simple logistic baseline and a random forest.', 'Area under the curve 0.86 against 0.81 for the baseline; precision-recall area 0.71 against 0.63.', 'Calibration error 0.021. The cut-off is set so 9 in 10 large claims go to an adjuster.'] },
  ]
  const lookSections: FactSection[] = [
    { key: 'for', title: 'What it is for', body: ['Points out claims where a person in special investigations should take a closer look.', 'It shows the signs it found, each with where it came from, so the investigator can check them.'] },
    { key: 'not_for', title: 'What it is not for', body: ['It never denies a claim, and a sign is never a reason to deny one on its own.', 'It does not slow a claim down: the adjuster keeps working it while the investigator looks.'] },
    { key: 'looks_at', title: 'What it looks at', body: ['14 signs, such as a new policy, cover raised just before the loss, a late report, a story that changes, or someone else pushing for a fast payment.', 'Whether the weather record matches a storm claim, and whether a theft has a police report.'] },
    { key: 'never_looks_at', title: 'What it never looks at', body: ['Age, gender, language, region or postcode.', 'Names, date of birth, or anything about how a voice sounds: accent, pitch, stress or speed.'] },
    { key: 'tested', title: 'How it was tested', body: ['Learned from practice calls with losses before 1 October 2025 and tested on October to December 2025.', 'Investigators agreed with its flags 7 in 10 times in December, against 4 in 10 for random spot checks.'] },
    { key: 'limits', title: 'Known limits', body: ['During a storm, many honest claims share the same timing and damage, so we watch it more closely in storm weeks.', 'About 4 in 100 claims are flagged. Most flagged claims turn out fine, which is why a person always decides.'] },
    { key: 'fairness', title: 'Fairness', body: ['The closer-look rate for every region, language and age band is within 1.5 points of the overall 4.1 in 100.', FAIRNESS_NOTE] },
    { key: 'sign_offs', title: 'Sign-offs', body: ['Version 4 was signed off for claims by Renée Kowalchuk and for model risk by Priya Sandhu, and has been in use since 15 Dec 2025.', 'Version 5 has been on trial since 2 Jan. Renée Kowalchuk signed it off for claims on 6 Jan; the model risk sign-off from Priya Sandhu is still to come.'] },
    { key: 'technical', title: 'For the technical reviewer', body: ['Boosted decision trees with calibration, compared with a simple logistic baseline and a random forest.', 'Area under the curve 0.83 against 0.77 for the baseline; precision-recall area 0.34 against 0.26, at a base rate of about 4 in 100.', 'Calibration error 0.018. The cut-off keeps referrals under 8 in 100 claims.'] },
  ]

  const factSheets: Record<CheckKey, FactSheet> = {
    size: {
      key: 'size', name: 'Size check', version: 4, sections: sizeSections, versions: [sizeV4],
      technical: {
        test: SIZE_TEST, baseline: SIZE_BASE, randomForest: SIZE_RF,
        roc: curve(3.6), pr: prCurve(0.94, 0.12),
        calibration: calibration([612, 488, 351, 240, 188, 141, 102, 77, 51, 33], [0.01, -0.012, 0.018, -0.006, 0.021, -0.015, 0.009, -0.02, 0.014, -0.01]),
        split: SPLIT,
        features: ['Loss type', 'Damage described', 'Open to the weather', 'Car can be driven', 'Injury mentioned', 'Water still coming in', 'Police report', 'Photos sent', 'Caller\'s rough estimate', 'How long the policy has been active', 'Claims in the last 3 years', 'Storm confirmed by the weather record'],
      },
    },
    closer_look: {
      key: 'closer_look', name: 'Closer-look check', version: 4, sections: lookSections, versions: [lookV4, lookV5],
      technical: {
        test: LOOK_TEST, baseline: LOOK_BASE, randomForest: LOOK_RF,
        roc: curve(3.1), pr: prCurve(0.72, 0.04),
        calibration: calibration([1820, 210, 64, 28, 14, 9, 6, 4, 3, 2], [0.004, -0.01, 0.016, -0.02, 0.025, -0.03, 0.04, -0.035, 0.05, -0.05]),
        split: SPLIT,
        features: ['Days from policy start to the loss', 'Cover raised before the loss', 'Days from the loss to the report', 'Story changed during the call', 'Weather matches the loss', 'Theft without a police report', 'Round-number estimate', 'Someone else pushing for a fast payment', 'Claims in the last 3 years', 'Same repair shop or tow company as other recent claims', 'Damage that doesn\'t match the cause', 'Policy lapsed and reinstated', 'Caller unsure of basic details', 'Photos that don\'t match the description'],
      },
    },
  }

  const fairness: Record<CheckKey, Fairness> = {
    size: { key: 'size', version: 4, overallRate: 0.58, band: 0.05, passed: true, rows: fairnessRows(FAST_RATES, 0.58, 0.05, 0.93, 0.08), note: FAIRNESS_NOTE },
    closer_look: { key: 'closer_look', version: 4, overallRate: lookOverall, band: lookBand, passed: true, rows: fairnessRows(LOOK_RATES, lookOverall, lookBand, 0.62, 0.025), note: FAIRNESS_NOTE },
  }

  return {
    routingChecks,
    checks: { size, closer_look: look },
    factSheets,
    fairness,
  }
}
