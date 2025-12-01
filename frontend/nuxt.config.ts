import tailwindcss from '@tailwindcss/vite'

// ClaimVoice web app. Bare shell: the visual design lands in frontend/DESIGN.md and app/ components.
// The browser talks to the API through the same origin: server/routes/api/[...].ts forwards /api/** (including the
// supervisor event stream) to the Litestar API on :8040. The voice WebSocket fallback connects to the API directly.
const apiOrigin = process.env.CLAIMVOICE_API_ORIGIN ?? 'http://127.0.0.1:8040'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  future: { compatibilityVersion: 4 },
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  modules: ['@vueuse/nuxt'],
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      htmlAttrs: { lang: 'en' },
      title: 'ClaimVoice',
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    },
  },
  devServer: { port: 3040 },
  runtimeConfig: {
    apiOrigin,
  },
  vite: {
    plugins: [tailwindcss()],
  },
  typescript: { strict: true, typeCheck: false },
})
