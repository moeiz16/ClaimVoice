// "Where did we hear that?" Field ↔ span linking: hover or focus a claim-file value and its words light up (and
// scroll into view); hover a span and its field lights. A click flashes both (Pluck's reduced fallback is the same
// 1.6 s highlight).
export interface LinkTarget { turnId: string, start: number, end: number }

export function linkKey(t: LinkTarget | null | undefined): string | null {
  return t ? `${t.turnId}:${t.start}-${t.end}` : null
}

export function useHeardLinks() {
  const active = useState<string | null>('cv-heard-active', () => null)
  const flashKey = useState<string | null>('cv-heard-flash', () => null)
  let timer: ReturnType<typeof setTimeout> | null = null

  function hover(t: LinkTarget | null) { active.value = linkKey(t) }

  function flash(t: LinkTarget | null, scroll = true) {
    const key = linkKey(t)
    flashKey.value = key
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { flashKey.value = null }, 1600)
    if (scroll && key) {
      nextTick(() => {
        const el = document.querySelector(`[data-span="${CSS.escape(key)}"]`)
        el?.scrollIntoView({ block: 'center', behavior: usePrefs().reduceMotion.value ? 'auto' : 'smooth' })
      })
    }
  }

  const isActive = (t: LinkTarget | null | undefined) => {
    const k = linkKey(t)
    return !!k && (active.value === k || flashKey.value === k)
  }

  return { active, flashKey, hover, flash, isActive }
}
