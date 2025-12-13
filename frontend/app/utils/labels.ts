// Visual vocabulary for codes the API sends with their own labels. The API's *Label fields are always the words we
// show; this only picks the icon and tint that travel with them.
import type { Route } from '~/types/api'

export function routeStyle(route: Route | 'closer_look'): { kind: 'fast' | 'adj' | 'siu', icon: string, label: string } {
  switch (route) {
    case 'fast_track': return { kind: 'fast', icon: 'check', label: 'Fast-track' }
    case 'adjuster': return { kind: 'adj', icon: 'person', label: 'Adjuster' }
    default: return { kind: 'siu', icon: 'look', label: 'Closer look' }
  }
}

/** Icon for a loss type key. */
export function lossIcon(lossType: string | null | undefined): string {
  switch (lossType) {
    case 'collision': return 'car'
    case 'wind': return 'wind'
    case 'hail': return 'hail'
    case 'water': return 'drop'
    case 'fire': return 'fire'
    case 'theft': return 'key'
    default: return 'doc'
  }
}

/** Icon for a claim-file section. */
export function sectionIcon(key: string): string {
  return ({ caller: 'person', policy: 'doc', loss: 'wind', details: 'home', safety: 'heart', photos: 'camera', coverage: 'shield', next_steps: 'clock' } as Record<string, string>)[key] ?? 'doc'
}

/** Icon for a claim slip key on the landing call. */
export function slipIcon(key: string): string {
  return ({
    consent: 'shield', policy: 'check', where: 'pin', hurt: 'heart', skylight: 'home', debris: 'wind', when: 'wind',
    card: 'card', photos: 'camera', claimno: 'doc', car: 'car', water: 'drop', covered: 'home', readback: 'doc', glass: 'home',
  } as Record<string, string>)[key] ?? 'check'
}

/** Rubric bead icons, by rubric key. */
export function beadIcon(key: string): string {
  return ({
    consent_first: 'shield', identity_verified: 'person', required_fields: 'doc', empathy: 'heart', no_card_numbers: 'card', handoff_correct: 'handoff',
  } as Record<string, string>)[key] ?? 'check'
}

/** Plain words for a band ("Working as expected") already come from the API; pick the tint and icon. */
export function statusStyle(status: 'healthy' | 'watch' | 'act' | 'stable'): { kind: 'fast' | 'siu' | 'urgent', icon: string } {
  if (status === 'healthy' || status === 'stable') return { kind: 'fast', icon: 'check' }
  if (status === 'watch') return { kind: 'siu', icon: 'clock' }
  return { kind: 'urgent', icon: 'urgent' }
}

export const ROLE_OPTIONS: { role: 'admin' | 'supervisor' | 'intake_agent' | 'adjuster' | 'siu_investigator' | 'compliance', label: string, person: string, blurb: string }[] = [
  { role: 'supervisor', label: 'Claims supervisor', person: 'Renée Kowalchuk', blurb: 'Runs the lines: listens, whispers, takes over' },
  { role: 'adjuster', label: 'Adjuster', person: 'Lena Ortiz', blurb: 'Works claims after the call' },
  { role: 'siu_investigator', label: 'Special investigator', person: 'Dev Malhotra', blurb: 'Reviews closer-look referrals' },
  { role: 'compliance', label: 'Compliance and quality', person: 'Priya Sandhu', blurb: 'Routing checks, sign-offs, audit' },
  { role: 'intake_agent', label: 'Intake agent', person: 'Jamal Haddad', blurb: 'Takes hand-offs from the line' },
  { role: 'admin', label: 'Administrator', person: 'Nadia Kassem', blurb: 'People, scripts, consent and retention' },
]
