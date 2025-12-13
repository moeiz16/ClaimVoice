import tailwindcss from '@tailwindcss/vite'

// ClaimVoice web app ("On the line", frontend/DESIGN.md). Client-rendered; the browser talks to the API through the
// same origin: server/routes/api/[...].ts forwards /api/** (including the event streams) to the Litestar API on
// :8040. The voice WebSocket fallback connects to the API directly.
const apiOrigin = process.env.CLAIMVOICE_API_ORIGIN ?? 'http://127.0.0.1:8040'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  future: { compatibilityVersion: 4 },
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  modules: ['@vueuse/nuxt'],
  css: ['~/assets/css/main.css'],
  components: [{ path: '~/components', pathPrefix: false }],
  app: {
    pageTransition: { name: 'page', mode: 'out-in' },
    head: {
      htmlAttrs: { 'lang': 'en', 'data-theme': 'light' },
      title: 'ClaimVoice',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'ClaimVoice answers your claims line at any hour, in English or French, and hands your team a claim file where every detail links back to the words it came from.' },
        { name: 'theme-color', content: '#FBF7F9' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&family=Figtree:ital,wght@0,300..900;1,400..600&display=swap' },
      ],
    },
  },
  devServer: { port: 3040 },
  runtimeConfig: {
    apiOrigin,
    public: { apiMock: '' },
  },
  vite: {
    plugins: [tailwindcss()],
  },
  typescript: { strict: true, typeCheck: false },
})
