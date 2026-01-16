// One waveform grammar everywhere (DESIGN.md §11): a horizontal centre line; ClaimVoice and Larkspur people above, the
// caller below; bars 3 px wide, 2 px gap, fully rounded; played portion full colour, unplayed 32%; hush = hatched band
// plus a dotted line.

export type Who = 'cv' | 'caller' | 'person' | 'gap' | 'hush'
export interface WaveBar { who: Who, a: number }
export interface WaveTurn { who: Who, from: number, to: number }
export interface WaveColors { cv: string, caller: string, person: string, gap: string, hush: string, hushBand: string }

/** Small deterministic PRNG (mulberry32), so every render of the same call looks the same. */
export function rng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** A stable seed from a string (call ids, claim numbers). */
export function seedOf(text: string): number {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  return h >>> 0
}

/** Bar data for a conversation from turns over `duration` seconds, `n` bars. Speech-like envelope per turn. */
export function conversationBars(turns: WaveTurn[], duration: number, n: number, seed = 7): WaveBar[] {
  const r = rng(seed)
  const bars: WaveBar[] = []
  for (let i = 0; i < n; i++) {
    const t = ((i + 0.5) / n) * duration
    const turn = turns.find(x => t >= x.from && t < x.to)
    if (!turn) { bars.push({ who: 'gap', a: 0.03 + r() * 0.03 }); continue }
    if (turn.who === 'hush') { bars.push({ who: 'hush', a: 0 }); continue }
    const p = (t - turn.from) / Math.max(0.001, turn.to - turn.from)
    const env = Math.sin(Math.PI * Math.min(1, p * 1.15)) ** 0.6
    const syll = 0.55 + 0.45 * Math.abs(Math.sin(t * 9.3 + r() * 2))
    bars.push({ who: turn.who, a: Math.max(0.08, Math.min(1, env * syll * (0.65 + r() * 0.45))) })
  }
  return bars
}

/** Split hush stretches out of speaker turns: a turn with `hush` at t becomes speech until t, then a hush band. */
export function withHushes<T extends { who: Who, from: number, to: number, hush?: number | null }>(turns: T[]): WaveTurn[] {
  return turns.flatMap(x => (x.hush != null && x.hush < x.to)
    ? [{ who: x.who, from: x.from, to: x.hush }, { who: 'hush' as Who, from: x.hush, to: x.to }]
    : [{ who: x.who, from: x.from, to: x.to }])
}

export function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
  ctx.fill()
}

export function cssVar(name: string, el: Element = document.documentElement): string {
  return getComputedStyle(el).getPropertyValue(name).trim()
}

export function themeColors(): WaveColors {
  return {
    cv: cssVar('--cv-jade'),
    caller: cssVar('--cv-caller'),
    person: cssVar('--cv-person'),
    gap: cssVar('--cv-faint'),
    hush: cssVar('--cv-faint'),
    hushBand: cssVar('--cv-sunk-2'),
  }
}

/** Size a canvas for the device pixel ratio and return a scaled context with its CSS size. */
export function prepCanvas(canvas: HTMLCanvasElement): { ctx: CanvasRenderingContext2D, w: number, h: number } | null {
  const dpr = window.devicePixelRatio || 1
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (!w || !h) return null
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  canvas.width = Math.round(w * dpr)
  canvas.height = Math.round(h * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)
  return { ctx, w, h }
}

export interface DrawOpts { progress?: number, dim?: number, bar?: number, gap?: number, mid?: number, colors?: WaveColors }

/** Draw the conversation waveform: Larkspur's side above the line (mid), the caller below. */
export function drawConversation(canvas: HTMLCanvasElement, bars: WaveBar[], opts: DrawOpts = {}): void {
  const prep = prepCanvas(canvas)
  if (!prep || !bars.length) return
  const { ctx, w, h } = prep
  const { progress = 1, dim = 0.32, bar = 3, gap = 2, mid = 0.5 } = opts
  const c = opts.colors ?? themeColors()
  const step = bar + gap
  const n = Math.floor(w / step)
  const y0 = h * mid
  for (let i = 0; i < n; i++) {
    const b = bars[Math.floor((i / n) * bars.length)]!
    const x = i * step
    ctx.globalAlpha = i / n <= progress ? 1 : dim
    if (b.who === 'hush') {
      ctx.fillStyle = c.hushBand
      ctx.fillRect(x - gap / 2, 4, step, h - 8)
      ctx.fillStyle = c.hush
      if (i % 2 === 0) {
        ctx.save()
        ctx.globalAlpha *= 0.55
        ctx.fillRect(x, 4 + ((i * 7) % 12), 1.5, Math.max(1, h - 16))
        ctx.restore()
      }
      if (i % 3 === 0) ctx.fillRect(x, y0 - 1, bar, 2)
      continue
    }
    const up = b.who === 'cv' || b.who === 'person'
    const amp = b.a * (up ? y0 - 2 : h - y0 - 2)
    ctx.fillStyle = c[b.who as keyof WaveColors] ?? c.gap
    const hh = Math.max(2, amp)
    roundRect(ctx, x, up ? y0 - hh - 1 : y0 + 1, bar, hh, Math.min(bar / 2, hh / 2))
  }
  ctx.globalAlpha = 1
}

/** A ring buffer of live bars, newest at the end (drawn at the right edge, older bars fading to 35%). */
export class LiveBars {
  readonly size: number
  private items: WaveBar[] = []
  constructor(size: number, fill: WaveBar = { who: 'gap', a: 0.04 }) {
    this.size = Math.max(1, size)
    for (let i = 0; i < this.size; i++) this.items.push({ ...fill })
  }

  push(bar: WaveBar): void {
    this.items.push(bar)
    if (this.items.length > this.size) this.items.splice(0, this.items.length - this.size)
  }

  resize(size: number): void {
    const s = Math.max(1, size)
    while (this.items.length < s) this.items.unshift({ who: 'gap', a: 0.04 })
    if (this.items.length > s) this.items.splice(0, this.items.length - s)
    ;(this as { size: number }).size = s
  }

  get bars(): readonly WaveBar[] { return this.items }
}

export function drawLive(canvas: HTMLCanvasElement, bars: readonly WaveBar[], opts: { bar?: number, gap?: number, colors?: WaveColors } = {}): void {
  const prep = prepCanvas(canvas)
  if (!prep) return
  const { ctx, w, h } = prep
  const { bar = 2.5, gap = 2 } = opts
  const c = opts.colors ?? themeColors()
  const step = bar + gap
  const n = Math.min(bars.length, Math.floor(w / step))
  const y0 = h / 2
  const offset = bars.length - n
  for (let i = 0; i < n; i++) {
    const b = bars[offset + i]!
    const up = b.who === 'cv' || b.who === 'person'
    const hh = Math.max(1.5, b.a * (y0 - 1))
    ctx.fillStyle = c[b.who as keyof WaveColors] ?? c.gap
    ctx.globalAlpha = 0.35 + 0.65 * (i / Math.max(1, n))
    roundRect(ctx, i * step, up ? y0 - hh : y0, bar, hh, Math.min(bar / 2, hh / 2))
  }
  ctx.globalAlpha = 1
}

/** RMS of a time-domain frame, mapped to 0..1 with a soft knee so quiet speech still shows. */
export function rmsLevel(frame: Float32Array): number {
  if (!frame.length) return 0
  let sum = 0
  for (let i = 0; i < frame.length; i++) sum += frame[i]! * frame[i]!
  const rms = Math.sqrt(sum / frame.length)
  return Math.max(0, Math.min(1, Math.sqrt(rms) * 1.8))
}

/** Map a 0..1 level to the reduced-motion 5-step meter. */
export function levelStep(level: number): number {
  return Math.max(0, Math.min(5, Math.round(level * 5)))
}

/**
 * Split mono recording peaks into two lanes by who was speaking (Recording.segments): ClaimVoice/people above,
 * the caller below. Peaks in hushed stretches become null (drawn hatched).
 */
export function splitPeaks(
  peaks: number[],
  duration: number,
  segments: { speaker: string, startSeconds: number, endSeconds: number }[],
  hushes: [number, number][] = [],
): { line: number[], caller: number[], hushed: boolean[] } {
  const line: number[] = []
  const caller: number[] = []
  const hushed: boolean[] = []
  const n = peaks.length
  for (let i = 0; i < n; i++) {
    const t = ((i + 0.5) / n) * duration
    const v = Math.abs(peaks[i] ?? 0)
    const isHush = hushes.some(([a, b]) => t >= a && t < b)
    hushed.push(isHush)
    if (isHush) { line.push(0); caller.push(0); continue }
    const seg = segments.find(s => t >= s.startSeconds && t < s.endSeconds)
    if (seg?.speaker === 'caller') { caller.push(v); line.push(0) }
    else if (seg) { line.push(v); caller.push(0) }
    else { line.push(Math.min(v, 0.04)); caller.push(Math.min(v, 0.04)) }
  }
  return { line, caller, hushed }
}

/**
 * Synthetic level for a live line at time t (seconds) when the server sends no audio levels (browser_speech calls):
 * driven by whose turn it is, with a speech-like syllable rhythm.
 */
export function syntheticLevel(who: Who, t: number, r: () => number): number {
  if (who === 'gap' || who === 'hush') return 0.04
  return Math.min(1, 0.25 + 0.75 * Math.abs(Math.sin(t * 7.1 + r() * 1.5)) * (0.6 + r() * 0.5))
}

/** A default "who is speaking" rhythm for a live line: caller ~5.5 s, pause, ClaimVoice ~5.4 s, pause. */
export function defaultRhythm(seed: number): (t: number) => Who {
  const phase = rng(seed)() * 13
  return (t: number) => {
    const ph = (t + phase) % 13
    return ph < 5.5 ? 'caller' : ph < 6.6 ? 'gap' : ph < 12 ? 'cv' : 'gap'
  }
}
