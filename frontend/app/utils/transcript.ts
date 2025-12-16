// Transcript text → render segments. The transcript is the source of truth; claim-file values point into it with
// character offsets. Caller text is untrusted: we never render it as HTML, only as text segments.

export const CARD_TOKEN = '[card number removed]'

export interface Mark { start: number, end: number, key: string, kind?: 'heard' | 'sign' }
export type Segment =
  | { type: 'text', text: string }
  | { type: 'span', text: string, key: string, kind: 'heard' | 'sign' }
  | { type: 'sound', text: string }
  | { type: 'hush' }

/** Find a phrase in a text (case-insensitive), returning character offsets or null. */
export function findPhrase(text: string, phrase: string): { start: number, end: number } | null {
  if (!phrase) return null
  const i = text.toLowerCase().indexOf(phrase.toLowerCase())
  return i < 0 ? null : { start: i, end: i + phrase.length }
}

/** Split plain text into text, sound tags ("[dog barking]") and hush pills ("[card number removed]"). */
function splitInline(text: string): Segment[] {
  const out: Segment[] = []
  const re = /\[([^\]]{1,60})\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ type: 'text', text: text.slice(last, m.index) })
    if (m[0].toLowerCase() === CARD_TOKEN || /card number|numéro de carte/i.test(m[1]!)) out.push({ type: 'hush' })
    else out.push({ type: 'sound', text: m[0] })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ type: 'text', text: text.slice(last) })
  return out
}

/**
 * Turn a transcript text and its marks (heard spans, closer-look phrases) into ordered segments. Overlapping marks are
 * resolved first-come; out-of-range marks are clamped or dropped.
 */
export function segmentText(text: string, marks: Mark[] = []): Segment[] {
  const valid = marks
    .map(m => ({ ...m, start: Math.max(0, m.start), end: Math.min(text.length, m.end) }))
    .filter(m => m.end > m.start)
    .sort((a, b) => a.start - b.start)
  const out: Segment[] = []
  let cursor = 0
  for (const m of valid) {
    if (m.start < cursor) continue
    if (m.start > cursor) out.push(...splitInline(text.slice(cursor, m.start)))
    out.push({ type: 'span', text: text.slice(m.start, m.end), key: m.key, kind: m.kind ?? 'heard' })
    cursor = m.end
  }
  if (cursor < text.length) out.push(...splitInline(text.slice(cursor)))
  return out
}

/** Index of the turn being spoken at time t (seconds), or the last one started; -1 before the first. */
export function turnAt<T extends { from: number }>(turns: T[], t: number): number {
  let idx = -1
  for (let i = 0; i < turns.length; i++) if (turns[i]!.from <= t) idx = i
  return idx
}

/** Same for transcript turns timed in milliseconds. */
export function turnAtMs<T extends { atMs: number }>(turns: T[], ms: number): number {
  let idx = -1
  for (let i = 0; i < turns.length; i++) if (turns[i]!.atMs <= ms) idx = i
  return idx
}

/** Remove the "[card number removed]" token (the hush pill stands in for it). */
export function stripCardToken(text: string): string {
  return text.replace(/\s*\[card number removed\]\s*/gi, ' ').replace(/\s*\[numéro de carte retiré\]\s*/gi, ' ').trim()
}

/** Seconds at which the last word of `phrase` is spoken in a turn (words spread evenly), or null if absent. */
export function phraseSpokenAt(turn: { text: string, from: number, to: number, hush?: number | null }, phrase: string): number | null {
  const norm = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}'-]/gu, '')
  const toks = stripCardToken(turn.text).split(/\s+/).filter(Boolean).map(norm)
  const sw = phrase.split(/\s+/).filter(Boolean).map(norm)
  const end = turn.hush ?? turn.to
  for (let i = 0; i + sw.length <= toks.length; i++) {
    if (sw.every((w, j) => toks[i + j] === w)) return turn.from + ((i + sw.length - 0.5) / Math.max(1, toks.length)) * (end - turn.from)
  }
  return null
}

export interface KaraokeWord { text: string, ahead: boolean, span: string | null, spanStart: boolean, spanEnd: boolean }

/**
 * Karaoke for the lyric sheet: spoken words in full ink, the rest wait faintly; a heard span is marked once all its
 * words have been spoken. Words are spread evenly between `from` and the hush (or `to`).
 */
export function karaoke(
  turn: { text: string, from: number, to: number, hush?: number | null, spans?: { text: string, key: string }[] },
  now: number,
): { words: KaraokeWord[], hushed: boolean } {
  const toks = stripCardToken(turn.text).split(/\s+/).filter(Boolean)
  const n = toks.length
  const end = turn.hush ?? turn.to
  const at = (i: number) => turn.from + ((i + 0.5) / Math.max(1, n)) * (end - turn.from)
  const norm = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}'-]/gu, '')
  const spanOf: (string | null)[] = Array(n).fill(null)
  const startOf: boolean[] = Array(n).fill(false)
  const endOf: boolean[] = Array(n).fill(false)
  for (const s of turn.spans ?? []) {
    const sw = s.text.split(/\s+/).filter(Boolean).map(norm)
    for (let i = 0; i + sw.length <= n; i++) {
      if (sw.every((w, j) => norm(toks[i + j]!) === w)) {
        if (at(i + sw.length - 1) <= now) {
          for (let j = 0; j < sw.length; j++) spanOf[i + j] = s.key
          startOf[i] = true
          endOf[i + sw.length - 1] = true
        }
        break
      }
    }
  }
  return {
    words: toks.map((w, i) => ({ text: w, ahead: now < at(i), span: spanOf[i]!, spanStart: startOf[i]!, spanEnd: endOf[i]! })),
    hushed: turn.hush != null && now >= turn.hush,
  }
}

/** Group consecutive karaoke words into runs so a heard span renders as one mark. */
export function karaokeRuns(words: KaraokeWord[]): { span: string | null, words: KaraokeWord[] }[] {
  const runs: { span: string | null, words: KaraokeWord[] }[] = []
  for (const w of words) {
    const last = runs[runs.length - 1]
    if (last && last.span === w.span && !(w.span && w.spanStart)) last.words.push(w)
    else runs.push({ span: w.span, words: [w] })
  }
  return runs
}

/** Settle: split a live caption into final words and the interim tail (faint, settling into ink when final). */
export function settleSplit(finalText: string, interim: string): { final: string[], interim: string[] } {
  return {
    final: finalText.split(/\s+/).filter(Boolean),
    interim: interim.split(/\s+/).filter(Boolean),
  }
}
