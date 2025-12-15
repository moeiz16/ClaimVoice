// Per-viewer preferences: theme (Day line default, Night line on request; never follows the OS on first visit),
// interface language, caption size and the in-app "Reduce motion" setting. Stored in localStorage.
import { usePreferredReducedMotion, useStorage } from '@vueuse/core'
import { setUiLang } from '~/utils/http'

export type Theme = 'light' | 'dark'
export type CaptionSize = 's' | 'm' | 'l'

export function usePrefs() {
  const theme = useStorage<Theme>('cv-theme', 'light')
  const lang = useStorage<'en' | 'fr'>('cv-lang', 'en')
  const captions = useStorage<CaptionSize>('cv-captions', 'm')
  const reduceMotionSetting = useStorage<boolean>('cv-reduce-motion', false)
  const os = usePreferredReducedMotion()
  const reduceMotion = computed(() => reduceMotionSetting.value || os.value === 'reduce')

  function toggleTheme() { theme.value = theme.value === 'dark' ? 'light' : 'dark' }

  return { theme, lang, captions, reduceMotionSetting, reduceMotion, toggleTheme }
}

/** Apply the preferences to <html> (called once from app.vue). URL flags ?theme= and ?still win for screenshots. */
export function applyPrefs() {
  const prefs = usePrefs()
  const route = useRoute()
  if (typeof route.query.theme === 'string' && (route.query.theme === 'light' || route.query.theme === 'dark')) prefs.theme.value = route.query.theme
  if ('still' in route.query) prefs.reduceMotionSetting.value = true
  watchEffect(() => {
    const el = document.documentElement
    el.dataset.theme = prefs.theme.value
    el.dataset.captions = prefs.captions.value
    el.classList.toggle('reduce-motion', prefs.reduceMotion.value)
    setUiLang(prefs.lang.value)
  })
  return prefs
}

/** True when motion should be replaced by its reduced fallback. */
export function useReducedMotionPref() {
  return usePrefs().reduceMotion
}
