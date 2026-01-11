// ClaimVoice web app ("The switchboard", frontend/DESIGN.md §0). Client-rendered; the browser talks to the API
// through the same origin: server/routes/api/[...].ts forwards /api/** (including the event streams) to the Litestar
// API on :8040. The voice WebSocket fallback connects to the API directly.
//
// Component system: Nuxt UI 3 (Reka UI + Tailwind 4), themed in app.config.ts and assets/css/main.css. Nuxt UI
// registers the Tailwind Vite plugin itself. Fonts are self-hosted from @fontsource (no font CDN), icons are
// bundled into the client from @iconify-json/lucide (no icon API at runtime).
const apiOrigin = process.env.CLAIMVOICE_API_ORIGIN ?? 'http://127.0.0.1:8040'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  future: { compatibilityVersion: 4 },
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  modules: ['@nuxt/ui', '@vueuse/nuxt'],
  css: ['~/assets/css/main.css'],
  components: [{ path: '~/components', pathPrefix: false }],
  ui: {
    fonts: false,
    colorMode: false,
    theme: { colors: ['primary', 'secondary', 'success', 'info', 'warning', 'error'] },
  },
  icon: {
    provider: 'none',
    serverBundle: false,
    clientBundle: {
      // Icon names written as 'i-lucide-…' in components and utils (labels, the board's lamps) are bundled.
      scan: { globInclude: ['app/**/*.{vue,ts}'], globExclude: ['node_modules', '.nuxt', '.output', 'tests'] },
      // Icons Nuxt UI's components use internally (appConfig.ui.icons) are not in our sources, so list them.
      icons: [
        'lucide:x', 'lucide:check', 'lucide:chevron-down', 'lucide:chevron-up', 'lucide:chevron-left', 'lucide:chevron-right',
        'lucide:chevrons-left', 'lucide:chevrons-right', 'lucide:ellipsis', 'lucide:search', 'lucide:loader-circle',
        'lucide:minus', 'lucide:plus', 'lucide:arrow-left', 'lucide:arrow-right', 'lucide:arrow-up', 'lucide:arrow-down',
        'lucide:circle-x', 'lucide:circle-check', 'lucide:circle-alert', 'lucide:info', 'lucide:triangle-alert',
        'lucide:copy', 'lucide:copy-check', 'lucide:grip-vertical', 'lucide:upload', 'lucide:file', 'lucide:eye', 'lucide:eye-off',
        'lucide:panel-left-close', 'lucide:panel-left-open', 'lucide:menu', 'lucide:sun', 'lucide:moon', 'lucide:monitor',
        'lucide:square', 'lucide:hash', 'lucide:external-link',
      ],
      sizeLimitKb: 512,
    },
  },
  app: {
    pageTransition: { name: 'page', mode: 'out-in' },
    head: {
      htmlAttrs: { 'lang': 'en', 'data-theme': 'light', 'class': 'light' },
      title: 'ClaimVoice',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'ClaimVoice answers your claims line at any hour, in English or French, and hands your team a claim file where every detail links back to the words it came from.' },
        { name: 'theme-color', content: '#FBF7F9' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
      ],
    },
  },
  devServer: { port: 3040 },
  runtimeConfig: {
    apiOrigin,
    public: { apiMock: '' },
  },
  // One server bundle: with chunked output this Nitro release reads public assets relative to the chunk, not the
  // server directory, so /_nuxt files fail to load in `npm run preview`. The server is only the SPA shell and the API proxy.
  nitro: { inlineDynamicImports: true },
  typescript: { strict: true, typeCheck: false },
})
