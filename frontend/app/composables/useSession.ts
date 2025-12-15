// The signed-in person, their role and permissions, and the server's clock. Public pages use GET /auth/session
// (always 200); the app pages require a session and go to sign-in (returning afterwards) when it ends.
import type { Me, Role } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

/** Where each role lands after signing in (contract §1.3). */
export function landingFor(me: Pick<Me, 'membership' | 'user'> | null): string {
  const role = me?.membership?.role
  switch (role) {
    case 'admin': return '/settings'
    case 'adjuster': return '/claims'
    case 'siu_investigator': return '/claims?route=special_investigation'
    case 'compliance': return me?.user.fullName.startsWith('Owen') ? '/quality' : '/routing'
    default: return '/lines'
  }
}

/** Which dock destinations a set of permissions can see. */
export function navFor(perms: string[]): { lines: boolean, claims: boolean, quality: boolean, routing: boolean, settings: boolean } {
  const has = (p: string) => perms.includes(p)
  return { lines: has('lines:read'), claims: has('claims:read'), quality: has('qa:read'), routing: has('models:read'), settings: has('settings:read') }
}

export function useSession() {
  const me = useState<Me | null>('cv-me', () => null)
  const loaded = useState<boolean>('cv-me-loaded', () => false)

  async function load(force = false): Promise<Me | null> {
    if (loaded.value && !force) return me.value
    try {
      const s = await api.auth.session()
      me.value = s.me
    }
    catch {
      me.value = null
    }
    loaded.value = true
    return me.value
  }

  async function signIn(email: string, password: string): Promise<Me> {
    const m = await api.auth.login(email, password)
    me.value = m
    loaded.value = true
    return m
  }

  async function demo(role: Role): Promise<Me> {
    const m = await api.auth.demo(role)
    me.value = m
    loaded.value = true
    return m
  }

  async function signOut(): Promise<void> {
    try { await api.auth.logout() }
    catch { /* already signed out */ }
    me.value = null
  }

  const permissions = computed(() => me.value?.membership?.permissions ?? [])
  const can = (perm: string) => permissions.value.includes(perm)
  const role = computed<Role | null>(() => me.value?.membership?.role ?? null)
  const firstName = computed(() => me.value?.user.fullName.split(' ')[0] ?? '')

  return { me, loaded, load, signIn, demo, signOut, permissions, can, role, firstName }
}

/** Treat a 401 from any page fetch the way the contract says: go to sign-in, then come back. */
export function isSessionEnded(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401
}
