// The local mock API is opt-in (NUXT_PUBLIC_API_MOCK=1, or ?mock=1 in development). Without it the app talks to the
// real API through the same-origin /api proxy.
import { setMockMode } from '~/utils/http'

export default defineNuxtPlugin({
  name: 'claimvoice-mock',
  enforce: 'pre',
  setup() {
    const config = useRuntimeConfig()
    const flag = String(config.public.apiMock ?? '')
    let on = flag === '1' || flag === 'true'
    if (import.meta.dev) {
      const q = new URLSearchParams(window.location.search).get('mock')
      if (q === '1') sessionStorage.setItem('cv-mock', '1')
      if (q === '0') sessionStorage.removeItem('cv-mock')
      on = on || sessionStorage.getItem('cv-mock') === '1'
    }
    setMockMode(on)
  },
})
