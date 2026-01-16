// The places in ClaimVoice, each named by the question it answers (DESIGN.md §2–3). The question is the page's
// heading and the item in the Questions sheet; the short name is how people say it ("open Claims").

export type PlaceKey = 'lines' | 'claims' | 'quality' | 'routing' | 'settings' | 'activity'

export interface Place {
  key: PlaceKey
  to: string
  name: string
  question: string
  icon: string
  /** Keyboard shortcut after G. */
  key2: string | null
  /** The permission that shows it. */
  perm: string
}

export const PLACES: Place[] = [
  { key: 'lines', to: '/lines', name: 'Lines', question: 'Who\'s on the line?', icon: 'i-lucide-audio-lines', key2: 'L', perm: 'lines:read' },
  { key: 'claims', to: '/claims', name: 'Claims', question: 'Which claims came in?', icon: 'i-lucide-file-text', key2: 'C', perm: 'claims:read' },
  { key: 'quality', to: '/quality', name: 'Quality', question: 'Which calls missed the mark?', icon: 'i-lucide-flag', key2: 'Q', perm: 'qa:read' },
  { key: 'routing', to: '/routing', name: 'Routing checks', question: 'Is routing working, and fair?', icon: 'i-lucide-scale', key2: 'R', perm: 'models:read' },
  { key: 'settings', to: '/settings', name: 'Settings', question: 'How should the line behave?', icon: 'i-lucide-sliders-horizontal', key2: 'S', perm: 'settings:read' },
  { key: 'activity', to: '/activity', name: 'Activity', question: 'Who did what, and when?', icon: 'i-lucide-link-2', key2: 'A', perm: 'audit:read' },
]

/** The places a set of permissions can open, in order. */
export function placesFor(perms: string[]): Place[] {
  return PLACES.filter(p => perms.includes(p.perm))
}

/** The place a path belongs to (a record page belongs to its list's place). */
export function placeOf(path: string): Place | null {
  return PLACES.find(p => path === p.to || path.startsWith(`${p.to}/`)) ?? null
}

/** The question for a place key. */
export function questionFor(key: PlaceKey): string {
  return PLACES.find(p => p.key === key)!.question
}
