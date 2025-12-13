// Plain-words formatting. Every displayed time is computed from a timestamp the API gave us (or demo time), shown in
// an explicit time zone: Calgary (America/Edmonton), Denver (America/Denver) or Montréal (America/Toronto). Never the
// browser's own zone, never an ISO stamp.
import type { Lang } from '~/types/api'

export const ORG_ZONE = 'America/Edmonton'

const ZONES: Record<string, { zone: string, label: string, labelFr: string }> = {
  'CA-AB': { zone: 'America/Edmonton', label: 'Calgary time', labelFr: 'heure de Calgary' },
  'US-CO': { zone: 'America/Denver', label: 'Denver time', labelFr: 'heure de Denver' },
  'CA-QC': { zone: 'America/Toronto', label: 'Montréal time', labelFr: 'heure de Montréal' },
}

export function zoneForRegion(region: string | null | undefined): string {
  return (region && ZONES[region]?.zone) || ORG_ZONE
}

export function zoneLabel(region: string | null | undefined, lang: Lang = 'en'): string {
  const z = (region && ZONES[region]) || ZONES['CA-AB']!
  return lang === 'fr' ? z.labelFr : z.label
}

/** 76 → "1:16"; 5 → "0:05"; negative and NaN read as 0. */
export function fmtClock(seconds: number | null | undefined): string {
  const s = Math.max(0, Math.floor(Number.isFinite(seconds as number) ? (seconds as number) : 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

/** 76 → "1 minute 16"; 384 → "6 minutes 24"; 45 → "45 seconds". */
export function fmtDurationWords(seconds: number, lang: Lang = 'en'): string {
  const s = Math.round(seconds)
  const m = Math.floor(s / 60)
  const r = s % 60
  if (lang === 'fr') {
    if (m === 0) return `${r} secondes`
    return r ? `${m} min ${String(r).padStart(2, '0')}` : `${m} minute${m > 1 ? 's' : ''}`
  }
  if (m === 0) return `${r} second${r === 1 ? '' : 's'}`
  const mins = `${m} minute${m === 1 ? '' : 's'}`
  return r ? `${mins} ${r}` : mins
}

interface Parts { weekday: string, weekdayShort: string, day: number, month: string, monthShort: string, year: number, hour: number, minute: number }

const WEEKDAYS_FR = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
const MONTHS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function toDate(value: string | number | Date): Date {
  return value instanceof Date ? value : new Date(value)
}

/** Calendar parts of an instant in a zone (deterministic: our own month and day names, Intl only for the numbers). */
export function zonedParts(value: string | number | Date, zone: string = ORG_ZONE): Parts {
  const d = toDate(value)
  const f = new Intl.DateTimeFormat('en-US', {
    timeZone: zone, year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', hourCycle: 'h23', weekday: 'short',
  })
  const p: Record<string, string> = {}
  for (const part of f.formatToParts(d)) p[part.type] = part.value
  const wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(p.weekday ?? 'Sun')
  const month = Number(p.month) - 1
  return {
    weekday: WEEKDAYS[wd]!,
    weekdayShort: WEEKDAYS[wd]!.slice(0, 3),
    day: Number(p.day),
    month: MONTHS[month]!,
    monthShort: MONTHS[month]!.slice(0, 3),
    year: Number(p.year),
    hour: Number(p.hour) % 24,
    minute: Number(p.minute),
  }
}

/** "7:42 a.m." (EN) or "7 h 42" (FR). */
export function fmtTime(value: string | number | Date, zone: string = ORG_ZONE, lang: Lang = 'en'): string {
  const p = zonedParts(value, zone)
  if (lang === 'fr') return `${p.hour} h ${String(p.minute).padStart(2, '0')}`
  const h12 = p.hour % 12 === 0 ? 12 : p.hour % 12
  return `${h12}:${String(p.minute).padStart(2, '0')} ${p.hour < 12 ? 'a.m.' : 'p.m.'}`
}

/** "Thursday 8 January" / "jeudi 8 janvier". */
export function fmtDayLong(value: string | number | Date, zone: string = ORG_ZONE, lang: Lang = 'en'): string {
  const p = zonedParts(value, zone)
  if (lang === 'fr') {
    const wd = WEEKDAYS_FR[WEEKDAYS.indexOf(p.weekday)]
    return `${wd} ${p.day} ${MONTHS_FR[MONTHS.indexOf(p.month)]}`
  }
  return `${p.weekday} ${p.day} ${p.month}`
}

/** "Wed 7 Jan". */
export function fmtDayShort(value: string | number | Date, zone: string = ORG_ZONE): string {
  const p = zonedParts(value, zone)
  return `${p.weekdayShort} ${p.day} ${p.monthShort}`
}

/** "Wed 7 Jan, 5:52 p.m.". */
export function fmtDayTime(value: string | number | Date, zone: string = ORG_ZONE): string {
  return `${fmtDayShort(value, zone)}, ${fmtTime(value, zone)}`
}

/** A calendar date "2025-12-27" → "27 Dec 2025" (no zone shift: it is already a local date). */
export function fmtDate(isoDate: string | null | undefined): string {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return ''
  return `${d} ${MONTHS[m - 1]!.slice(0, 3)} ${y}`
}

/** A calendar date → "Mon 5 Jan". */
export function fmtDateShort(isoDate: string | null | undefined): string {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return ''
  const wd = new Date(Date.UTC(y, m - 1, d)).getUTCDay()
  return `${WEEKDAYS[wd]!.slice(0, 3)} ${d} ${MONTHS[m - 1]!.slice(0, 3)}`
}

/** "Today", "Yesterday" or "Tuesday 6 January", relative to demo now, in the zone. */
export function fmtDayGroup(value: string | number | Date, now: Date, zone: string = ORG_ZONE): string {
  const a = zonedParts(value, zone)
  const b = zonedParts(now, zone)
  const key = (p: Parts) => p.year * 10000 + MONTHS.indexOf(p.month) * 100 + p.day
  const dayMs = 86_400_000
  if (key(a) === key(b)) return 'Today'
  const y = zonedParts(new Date(now.getTime() - dayMs), zone)
  if (key(a) === key(y)) return 'Yesterday'
  return `${a.weekday} ${a.day} ${a.month}`
}

/** Seconds between an instant and demo now (never negative). */
export function secondsSince(value: string | null | undefined, now: Date): number {
  if (!value) return 0
  const t = Date.parse(value)
  return Number.isNaN(t) ? 0 : Math.max(0, Math.floor((now.getTime() - t) / 1000))
}

/** "just now", "3 minutes ago", "2 hours ago". */
export function fmtAgo(value: string, now: Date): string {
  const s = secondsSince(value, now)
  if (s < 45) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`
  const h = Math.round(m / 60)
  return `${h} hour${h === 1 ? '' : 's'} ago`
}

/** 0.96 → "96 in 100"; with of=10 → "7 in 10". */
export function frequency(share: number, of = 100): string {
  return `${Math.round(Math.max(0, Math.min(1, share)) * of)} in ${of}`
}

/** 0.041 → "4.1%". */
export function pct(share: number, digits = 1): string {
  return `${(share * 100).toFixed(digits)}%`
}

/** 4000, "CAD" → "$4,000". */
export function money(amount: number, currency: 'CAD' | 'USD' = 'CAD'): string {
  const n = Math.round(amount).toLocaleString('en-US')
  return currency === 'USD' ? `US$${n}` : `$${n}`
}

/** "Renée Kowalchuk" → "RK". */
export function initials(name: string | null | undefined): string {
  if (!name) return '·'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1]![0] : ''
  return (first + last).toUpperCase()
}

/** ["Jamal", "Sofía", "Aurélie"] → "Jamal, Sofía and Aurélie". */
export function joinWords(items: string[], lang: Lang = 'en'): string {
  const and = lang === 'fr' ? 'et' : 'and'
  if (items.length <= 1) return items[0] ?? ''
  return `${items.slice(0, -1).join(', ')} ${and} ${items[items.length - 1]}`
}

/** First name of a full name. */
export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name
}

/** "**1,191 closed without needing an adjuster**" → segments with the emphasised phrase flagged. */
export function emphasis(text: string): { text: string, em: boolean }[] {
  const out: { text: string, em: boolean }[] = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), em: false })
    out.push({ text: m[1]!, em: true })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last), em: false })
  return out
}
