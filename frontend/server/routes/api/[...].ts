// Same-origin proxy to the ClaimVoice API, so session cookies, CSRF and the SSE stream work without CORS.
export default defineEventHandler((event) => {
  const { apiOrigin } = useRuntimeConfig(event)
  const target = new URL(event.path, apiOrigin as string)
  return proxyRequest(event, target.toString())
})
