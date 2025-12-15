// Small helpers the seed is written with: demo-time arithmetic, readable ids, transcript turns with computed timing,
// claim-file slots whose spans are found in the turn text, recordings with speech-like peaks, and photo scenes.
import type {
  CallEvent, ClaimFile, ClaimFileSection, FlagKind, Iso, IsoDate, Lang, Moment, MomentKind, PersonRef, Recording,
  RecordingSegment, Slot, SlotHistory, SlotSource, Speaker, StageInfo, TextSpan, Turn,
} from '~/types/api'

// ---------------------------------------------------------------- time

/** Fixed UTC offsets in January (no daylight saving): Calgary and Denver are UTC−7, Montréal UTC−5. */
export const TZ = { calgary: -7, denver: -7, montreal: -5 } as const

const HOUR = 3600_000
const DAY = 24 * HOUR

export interface Clock {
  now: Date
  /** ISO string `seconds` from now (negative = in the past). */
  iso(seconds: number): Iso
  /** Local wall-clock time `dayOffset` days from the demo day, in a zone, as a Date. "7:05" or "7:05:30". */
  at(dayOffset: number, hhmm: string, tz?: number): Date
  /** Same as `at`, as an ISO string. */
  atIso(dayOffset: number, hhmm: string, tz?: number): Iso
  /** Local calendar date `dayOffset` days from the demo day (YYYY-MM-DD). */
  date(dayOffset: number, tz?: number): IsoDate
  /** ISO string `seconds` after a moment. */
  plus(base: Date | Iso, seconds: number): Iso
  /** "7:42 a.m." for a moment, in a zone. */
  clockLabel(when: Date | Iso, tz?: number): string
  /** Seconds between a moment and now (positive when it is in the past). */
  ago(when: Date | Iso): number
}

function parseHms(hhmm: string): number {
  const parts = hhmm.split(':').map(p => Number(p))
  const h = parts[0] ?? 0
  const m = parts[1] ?? 0
  const s = parts[2] ?? 0
  return ((h * 60 + m) * 60 + s) * 1000
}

export function makeClock(now: Date): Clock {
  const nowMs = now.getTime()
  const localMidnight = (tz: number): number => Math.floor((nowMs + tz * HOUR) / DAY) * DAY
  const toDate = (v: Date | Iso): Date => (typeof v === 'string' ? new Date(v) : v)
  const at = (dayOffset: number, hhmm: string, tz: number = TZ.calgary): Date =>
    new Date(localMidnight(tz) + dayOffset * DAY + parseHms(hhmm) - tz * HOUR)
  return {
    now,
    iso: seconds => new Date(nowMs + seconds * 1000).toISOString(),
    at,
    atIso: (dayOffset, hhmm, tz) => at(dayOffset, hhmm, tz).toISOString(),
    date: (dayOffset, tz = TZ.calgary) => new Date(localMidnight(tz) + dayOffset * DAY).toISOString().slice(0, 10),
    plus: (base, seconds) => new Date(toDate(base).getTime() + seconds * 1000).toISOString(),
    clockLabel: (when, tz = TZ.calgary) => {
      const local = new Date(toDate(when).getTime() + tz * HOUR)
      const h24 = local.getUTCHours()
      const m = local.getUTCMinutes()
      const h12 = h24 % 12 === 0 ? 12 : h24 % 12
      return `${h12}:${String(m).padStart(2, '0')} ${h24 < 12 ? 'a.m.' : 'p.m.'}`
    },
    ago: when => Math.round((nowMs - toDate(when).getTime()) / 1000),
  }
}

/** Seconds into a call as "m:ss". */
export function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** "m:ss" into seconds. */
export function sec(mss: string): number {
  const [m, s] = mss.split(':').map(p => Number(p))
  return (m ?? 0) * 60 + (s ?? 0)
}

// ---------------------------------------------------------------- ids

const KIND = {
  org: '0a9a', user: 'face', membership: 'abba', call: 'ca11', claim: 'c1a1', turn: '7a1c', policy: 'b01c',
  holder: 'b01d', photo: 'f070', handoff: 'ba70', event: 'e7e7', sms: '5e5d', audit: 'a0d1', siu: '5105',
  surge: '5a9e', invite: '1a7e',
} as const
export type IdKind = keyof typeof KIND

/** A stable, readable, UUID-shaped id: uid('call', 1) → "ca11ca11-0000-4000-8000-000000000001". */
export function uid(kind: IdKind, n: number): string {
  const p = KIND[kind]
  return `${p}${p}-0000-4000-8000-${String(n).padStart(12, '0')}`
}

// ---------------------------------------------------------------- people

export interface Who { id: string, name: string, first: string }
const person = (n: number, name: string): Who => ({ id: uid('user', n), name, first: name.split(' ')[0] ?? name })
export const P = {
  nadia: person(1, 'Nadia Kassem'),
  renee: person(2, 'Renée Kowalchuk'),
  jamal: person(3, 'Jamal Haddad'),
  sofia: person(4, 'Sofía Herrera'),
  aurelie: person(5, 'Aurélie Fortin'),
  lena: person(6, 'Lena Ortiz'),
  dev: person(7, 'Dev Malhotra'),
  priya: person(8, 'Priya Sandhu'),
  owen: person(9, 'Owen Fairweather'),
} as const
export const ref = (w: Who): PersonRef => ({ id: w.id, name: w.name })

// ---------------------------------------------------------------- stages (Part 5: ten stages, seven steps)

const STEP_LABELS = ['Consent', 'Policy', 'Safety', 'What happened', 'Photos', 'Coverage', 'Read-back'] as const
const STAGES: [key: string, label: string, step: number][] = [
  ['greeting', 'Greeting', 1], ['consent', 'Recording consent', 1], ['identity', 'Caller and policy', 2],
  ['safety', 'Safety check', 3], ['loss_type', 'What happened', 4], ['loss_details', 'Details', 4],
  ['photos', 'Photos', 5], ['coverage', 'Coverage basics', 6], ['read_back', 'Read-back', 7], ['wrap_up', 'Wrap-up', 7],
]
export const STAGE_KEYS = STAGES.map(([key, label]) => ({ key, label }))

export function stage(key: string): StageInfo {
  if (key === 'handoff') return { key, label: 'With a person', step: 3, stepLabel: 'Safety', steps: 7, nextLabel: null }
  if (key === 'ended') return { key, label: 'Ended', step: 7, stepLabel: 'Read-back', steps: 7, nextLabel: null }
  const found = STAGES.find(s => s[0] === key)
  if (!found) throw new Error(`Seed: unknown stage ${key}`)
  const [, label, step] = found
  const next = STEP_LABELS[step]
  return { key, label, step, stepLabel: STEP_LABELS[step - 1] ?? label, steps: 7, nextLabel: next ? `${next} next` : null }
}

export const SCRIPTED_PATH: StageInfo[] = STAGES.map(([key]) => stage(key))

// ---------------------------------------------------------------- transcripts

export interface Line {
  who: Speaker
  text: string
  /** English under a French line. */
  en?: string
  /** Seconds into the call; omitted = shortly after the previous turn ends. */
  at?: number | string
  end?: number | string
  stage: string
  /** A name to find this turn by (slots, links, moments, evidence). */
  ref?: string
  /** Speaker label override (whispers, people, a second voice). */
  label?: string
  conf?: number
  interrupted?: boolean
  flags?: FlagKind[]
}

export const CARD = '[card number removed]'
const toSec = (v: number | string): number => (typeof v === 'string' ? sec(v) : v)

/** One call's turns with computed timing, looked up by `ref`. */
export class Talk {
  readonly turns: Turn[] = []
  private readonly refs = new Map<string, Turn>()

  constructor(
    readonly callId: string,
    readonly callNo: number,
    readonly language: Lang,
    readonly callerLabel: string,
    lines: Line[],
  ) {
    let prevEnd = 0
    lines.forEach((l, i) => {
      const next = lines[i + 1]
      const words = l.text.split(/\s+/).filter(Boolean).length
      const at = l.at != null ? toSec(l.at) : (i === 0 ? 0 : prevEnd + 0.6)
      let end = l.end != null ? toSec(l.end) : at + Math.max(1.2, words * 0.36 + 0.5)
      if (l.end == null && next?.at != null) end = Math.min(end, toSec(next.at) - 0.3)
      end = Math.max(end, at + 0.8)
      prevEnd = end
      const redactions = l.text.split(CARD).length - 1
      const lang: Lang = l.who === 'whisper' ? 'en' : this.language
      const turn: Turn = {
        id: uid('turn', callNo * 100 + i + 1),
        seq: i + 1,
        speaker: l.who,
        speakerLabel: l.label ?? (l.who === 'line' ? 'ClaimVoice' : l.who === 'caller' ? callerLabel : l.who === 'system' ? 'ClaimVoice notes' : 'Larkspur'),
        text: l.text,
        textEn: l.en ?? null,
        language: lang,
        atMs: Math.round(at * 1000),
        endMs: Math.round(end * 1000),
        stage: l.stage,
        confidence: l.who === 'caller' ? (l.conf ?? 0.93) : null,
        interrupted: l.interrupted ?? false,
        redactions,
        flags: l.flags ?? (redactions > 0 ? ['card_number_removed'] : []),
      }
      this.turns.push(turn)
      if (l.ref) this.refs.set(l.ref, turn)
    })
  }

  t(ref: string): Turn {
    const found = this.refs.get(ref)
    if (!found) throw new Error(`Seed: no turn "${ref}" in call ${this.callNo}`)
    return found
  }

  /** Seconds into the call where a turn starts. */
  sec(ref: string): number {
    return Math.floor(this.t(ref).atMs / 1000)
  }

  /** Character span of a phrase inside a turn's stored text. */
  span(ref: string, phrase: string): TextSpan {
    const t = this.t(ref)
    const start = t.text.indexOf(phrase)
    if (start < 0) throw new Error(`Seed: "${phrase}" is not in turn "${ref}" of call ${this.callNo}`)
    return { turnId: t.id, start, end: start + phrase.length }
  }

  /** The full sentence of a turn that contains the phrase (for quality evidence). */
  quote(ref: string, phrase: string): { turnId: string, quote: string } {
    const t = this.t(ref)
    const at = t.text.indexOf(phrase)
    if (at < 0) throw new Error(`Seed: "${phrase}" is not in turn "${ref}" of call ${this.callNo}`)
    return { turnId: t.id, quote: phrase }
  }

  /** Seconds of the last turn's end. */
  get endSeconds(): number {
    const last = this.turns[this.turns.length - 1]
    return last ? Math.ceil(last.endMs / 1000) : 0
  }
}

// ---------------------------------------------------------------- claim-file slots

export interface Src { source: SlotSource, sourceLabel: string, span: TextSpan | null, heardAtSeconds: number | null }

export function heard(talk: Talk, turnRef: string, phrase: string): Src {
  const s = talk.sec(turnRef)
  return { source: 'heard', sourceLabel: `▸ ${fmt(s)}`, span: talk.span(turnRef, phrase), heardAtSeconds: s }
}
export const fromPolicy = (): Src => ({ source: 'policy_record', sourceLabel: 'from the policy', span: null, heardAtSeconds: null })
export const lookedUp = (label = 'looked up'): Src => ({ source: 'tool', sourceLabel: label, span: null, heardAtSeconds: null })
export const editedBy = (w: Who): Src => ({ source: 'person', sourceLabel: `edited by ${w.name}`, span: null, heardAtSeconds: null })
export const notYet = (label = 'Not asked yet'): Src => ({ source: 'heard', sourceLabel: label, span: null, heardAtSeconds: null })

export interface SlotOpts {
  value?: unknown
  conf?: number
  required?: boolean
  confirmed?: boolean
  changedAt?: number | null
  history?: SlotHistory[]
}

export function slot(key: string, label: string, display: string, src: Src, o: SlotOpts = {}): Slot {
  const pending = display === ''
  const conf = pending ? null : (o.conf ?? (src.source === 'heard' ? 0.93 : null))
  const confidenceLabel = pending ? null : conf == null || conf >= 0.85 ? 'sure' : conf >= 0.6 ? 'likely' : 'check'
  return {
    key,
    label,
    value: pending ? null : (o.value ?? display),
    display,
    confidence: conf,
    confidenceLabel,
    source: src.source,
    sourceLabel: src.sourceLabel,
    span: src.span,
    heardAtSeconds: src.heardAtSeconds,
    changedAtSeconds: o.changedAt ?? null,
    confirmed: o.confirmed ?? (!pending && (conf == null || conf >= 0.85)),
    required: o.required ?? true,
    history: o.history ?? [],
  }
}

export function section(key: ClaimFileSection['key'], label: string, slots: Slot[]): ClaimFileSection {
  return { key, label, slots }
}

export function claimFile(callId: string, claimId: string | null, lossType: string | null, lossTypeLabel: string | null, sections: ClaimFileSection[]): ClaimFile {
  const all = sections.flatMap(s => s.slots)
  const filled = all.filter(s => s.display !== '')
  return {
    callId,
    claimId,
    lossType,
    lossTypeLabel,
    progress: all.length ? Math.round((filled.length / all.length) * 100) / 100 : 0,
    missing: all.filter(s => s.display === '' && s.required).map(s => s.label),
    sections,
  }
}

// ---------------------------------------------------------------- recordings

/** Small deterministic random numbers (mulberry32), so every build of the seed is identical. */
export function rng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** About `n` peaks (0..1) shaped like speech: a swell per turn, syllable ripple, silence between turns and in hushes. */
export function peaksFor(segments: RecordingSegment[], duration: number, seed: number, n = 800): number[] {
  const r = rng(seed)
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    const t = ((i + 0.5) / n) * duration
    const seg = segments.find(s => t >= s.startSeconds && t < s.endSeconds)
    if (!seg) { out.push(Math.round((0.02 + r() * 0.03) * 1000) / 1000); continue }
    if (seg.paused) { out.push(0); continue }
    const p = (t - seg.startSeconds) / Math.max(0.001, seg.endSeconds - seg.startSeconds)
    const env = Math.sin(Math.PI * Math.min(1, p * 1.12)) ** 0.6
    const syllable = 0.55 + 0.45 * Math.abs(Math.sin(t * 9.3 + r() * 2))
    const voice = seg.speaker === 'caller' ? 0.9 : 0.78
    const v = Math.max(0.08, Math.min(1, env * syllable * voice * (0.7 + r() * 0.4)))
    out.push(Math.round(v * 1000) / 1000)
  }
  return out
}

export function moment(kind: MomentKind, label: string, talk: Talk, turnRef: string, atSeconds?: number): Moment {
  return { kind, label, atSeconds: atSeconds ?? talk.sec(turnRef), turnId: talk.t(turnRef).id }
}

export interface RecordingOpts {
  seed: number
  moments: Moment[]
  hushes?: [number, number][]
  duration?: number
  audioUrl?: string | null
  retainedUntil: IsoDate | null
}

/** A recording built from a call's turns: one segment per spoken turn, hushes cut out as paused segments. */
export function recordingFrom(talk: Talk, o: RecordingOpts): Recording {
  const hushes = o.hushes ?? []
  const segments: RecordingSegment[] = []
  for (const t of talk.turns) {
    if (t.speaker === 'whisper') continue
    const speaker = t.speaker
    const start = t.atMs / 1000
    const end = t.endMs / 1000
    const cut = hushes.find(([a, b]) => a < end && b > start)
    if (!cut) { segments.push({ turnId: t.id, speaker, startSeconds: start, endSeconds: end, paused: false }); continue }
    const [a, b] = cut
    if (a > start) segments.push({ turnId: t.id, speaker, startSeconds: start, endSeconds: a, paused: false })
    segments.push({ turnId: t.id, speaker, startSeconds: Math.max(a, start), endSeconds: Math.min(b, end), paused: true })
    if (b < end) segments.push({ turnId: t.id, speaker, startSeconds: b, endSeconds: end, paused: false })
  }
  const duration = o.duration ?? talk.endSeconds + 1
  return {
    available: true,
    reason: null,
    audioUrl: o.audioUrl ?? null,
    durationSeconds: duration,
    peaks: peaksFor(segments, duration, o.seed),
    segments,
    moments: o.moments,
    hushes,
    retainedUntil: o.retainedUntil,
  }
}

// ---------------------------------------------------------------- call timeline

export function timelineFrom(talk: Talk, startedAt: Iso, clock: Clock, extras: Omit<CallEvent, 'id' | 'at'>[] = []): CallEvent[] {
  const events: Omit<CallEvent, 'id' | 'at'>[] = [{ atMs: 0, kind: 'answered', label: 'ClaimVoice answered', actor: 'ClaimVoice', data: {} }]
  let last = ''
  for (const t of talk.turns) {
    if (t.stage !== last && t.speaker === 'line') {
      const s = t.stage === 'handoff' ? stage('handoff') : stage(t.stage)
      events.push({ atMs: t.atMs, kind: 'stage', label: `Step ${s.step} · ${s.label}`, actor: 'ClaimVoice', data: { stage: t.stage } })
      last = t.stage
    }
    if (t.redactions > 0) {
      events.push({ atMs: t.atMs + 5000, kind: 'flag', label: 'Card number stopped and removed', actor: 'ClaimVoice', data: { kind: 'card_number_removed', turnId: t.id } })
    }
  }
  const all = [...events, ...extras].sort((a, b) => a.atMs - b.atMs)
  return all.map((e, i) => ({ ...e, id: uid('event', talk.callNo * 100 + i + 1), at: clock.plus(startedAt, e.atMs / 1000) }))
}

// ---------------------------------------------------------------- photos (simple painted scenes, no text)

export type Scene = 'roof' | 'siding' | 'skylight' | 'fence' | 'car_rear' | 'card' | 'basement' | 'pipe' | 'car_side' | 'shed'

const SKY: Record<string, [string, string]> = {
  dawn: ['#F3D9CF', '#B9A3C9'],
  grey: ['#D8DEE5', '#9CA9B6'],
  dusk: ['#3B3F66', '#8E7FA6'],
  room: ['#EFE6DA', '#CDBFAE'],
  garage: ['#C9CDD2', '#8B9198'],
}

function svgScene(scene: Scene, variant: number): string {
  const sky = scene === 'basement' || scene === 'pipe' || scene === 'skylight'
    ? SKY.room
    : scene === 'card' ? SKY.garage : [SKY.dawn, SKY.grey, SKY.dusk][variant % 3]
  const [top, bottom] = sky ?? ['#DDDDDD', '#999999']
  const shapes: Record<Scene, string> = {
    roof: '<rect y="210" width="400" height="90" fill="#7C8B6A"/><polygon points="70,150 200,70 330,150" fill="#5B4A4F"/><rect x="90" y="150" width="220" height="90" fill="#C9B79C"/><polygon points="150,104 196,78 220,92 176,118" fill="#A88E7A"/><polygon points="236,104 262,118 248,126 224,112" fill="#A88E7A"/><rect x="180" y="190" width="40" height="50" fill="#6E5A4C"/>',
    siding: '<rect y="230" width="400" height="70" fill="#7C8B6A"/><rect x="40" y="60" width="320" height="180" fill="#B8C4C9"/><g fill="#9FAEB4"><rect x="40" y="80" width="320" height="6"/><rect x="40" y="110" width="320" height="6"/><rect x="40" y="140" width="320" height="6"/></g><polygon points="210,150 300,165 290,232 200,220" fill="#E6E1D6"/><rect x="80" y="150" width="60" height="50" fill="#6D7F8C"/>',
    skylight: '<rect width="400" height="300" fill="#E9E1D3"/><rect x="120" y="50" width="160" height="120" fill="#8FA6BF"/><polygon points="120,50 200,110 160,170 120,170" fill="#A9BDD1"/><polygon points="280,50 220,120 280,140" fill="#C5D3E0"/><rect x="0" y="230" width="400" height="70" fill="#B59F84"/><g fill="#DCE6EE"><polygon points="160,250 172,244 176,256"/><polygon points="220,262 236,258 232,270"/><polygon points="250,244 258,240 262,250"/></g>',
    fence: '<rect y="200" width="400" height="100" fill="#7C8B6A"/><g fill="#A47E5B"><rect x="40" y="120" width="14" height="90"/><rect x="330" y="120" width="14" height="90"/></g><polygon points="60,200 330,150 336,170 66,222" fill="#B98F68"/><rect x="190" y="200" width="150" height="50" rx="14" fill="#4F6F8F"/><rect x="214" y="176" width="96" height="34" rx="10" fill="#6C8BAA"/><circle cx="220" cy="252" r="14" fill="#2E2E33"/><circle cx="312" cy="252" r="14" fill="#2E2E33"/>',
    car_rear: '<rect y="220" width="400" height="80" fill="#6F6E73"/><rect x="90" y="120" width="220" height="110" rx="22" fill="#9A3B3B"/><rect x="120" y="96" width="160" height="50" rx="16" fill="#B85656"/><rect x="104" y="186" width="192" height="26" rx="8" fill="#5A2626"/><polygon points="150,150 230,140 250,176 170,190" fill="#7C2E2E"/><circle cx="130" cy="232" r="18" fill="#2B2B2F"/><circle cx="270" cy="232" r="18" fill="#2B2B2F"/>',
    card: '<rect width="400" height="300" fill="#B8AFA4"/><rect x="100" y="80" width="200" height="130" rx="12" fill="#F4F1EA"/><rect x="118" y="100" width="90" height="12" rx="6" fill="#C9C2B6"/><rect x="118" y="124" width="140" height="10" rx="5" fill="#D9D3C8"/><rect x="118" y="144" width="120" height="10" rx="5" fill="#D9D3C8"/><rect x="230" y="160" width="52" height="34" rx="6" fill="#9FB4C9"/>',
    basement: '<rect width="400" height="300" fill="#D9D0C3"/><rect x="0" y="0" width="400" height="190" fill="#E4DCCF"/><rect x="40" y="70" width="90" height="120" fill="#B9AC9A"/><rect x="250" y="110" width="110" height="80" fill="#A79987"/><rect x="0" y="190" width="400" height="110" fill="#7FA3B5" opacity="0.85"/><g fill="#A6C3D1"><rect x="30" y="210" width="120" height="4" rx="2"/><rect x="200" y="236" width="150" height="4" rx="2"/></g>',
    pipe: '<rect width="400" height="300" fill="#CFC6B8"/><rect x="0" y="120" width="400" height="34" fill="#B07B4F"/><polygon points="196,120 214,120 206,154 192,154" fill="#5E3B22"/><g fill="#8FB5C8"><circle cx="205" cy="176" r="6"/><circle cx="198" cy="204" r="5"/><circle cx="210" cy="236" r="7"/></g><rect x="0" y="262" width="400" height="38" fill="#8DA9B6"/>',
    car_side: '<rect y="220" width="400" height="80" fill="#5E6066"/><rect x="60" y="140" width="280" height="80" rx="24" fill="#3F6A8A"/><polygon points="120,140 170,100 270,100 310,140" fill="#557F9F"/><polygon points="190,150 250,148 246,196 194,200" fill="#2D4E68"/><circle cx="120" cy="222" r="20" fill="#26262A"/><circle cx="290" cy="222" r="20" fill="#26262A"/>',
    shed: '<rect y="210" width="400" height="90" fill="#7C8B6A"/><rect x="130" y="130" width="140" height="90" fill="#A58A6A"/><polygon points="120,130 200,90 280,130" fill="#6B5B52"/><polygon points="230,104 300,90 310,104 238,118" fill="#857165"/><rect x="185" y="170" width="30" height="50" fill="#5E4B3B"/>',
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/><stop offset="1" stop-color="${bottom}"/></linearGradient></defs><rect width="400" height="300" fill="url(#g)"/>${shapes[scene]}</svg>`
}

export function sceneUrl(scene: Scene, variant = 0): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(svgScene(scene, variant))}`
}
