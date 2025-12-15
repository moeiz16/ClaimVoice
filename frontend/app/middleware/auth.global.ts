// App pages need a session; public pages (landing, demo line, sign-in, photo upload) don't. On a missing or ended
// session we go to sign-in and come back afterwards.
const PUBLIC = [/^\/$/, /^\/call\/?$/, /^\/sign-in\/?$/, /^\/p\//]

export default defineNuxtRouteMiddleware(async (to) => {
  if (PUBLIC.some(re => re.test(to.path))) return
  const { load, me, can } = useSession()
  const m = await load()
  if (!m) return navigateTo({ path: '/sign-in', query: { next: to.fullPath } })
  const needs: [RegExp, string][] = [
    [/^\/lines/, 'lines:read'], [/^\/claims/, 'claims:read'], [/^\/quality/, 'qa:read'], [/^\/routing/, 'models:read'],
    [/^\/settings/, 'settings:read'], [/^\/activity/, 'audit:read'],
  ]
  const rule = needs.find(([re]) => re.test(to.path))
  if (rule && !can(rule[1])) return navigateTo(landingFor(me.value))
})
