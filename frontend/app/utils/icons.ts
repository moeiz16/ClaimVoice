// ClaimVoice's icon vocabulary on lucide (bundled into the client; nuxt.config.ts `icon.clientBundle`). The short
// names are the ones the API-facing helpers in utils/labels.ts return; components pass `icon(name)` to Nuxt UI.
export const ICON: Record<string, string> = {
  play: 'i-lucide-play', pause: 'i-lucide-pause', listen: 'i-lucide-headphones', whisper: 'i-lucide-message-square-more',
  phone: 'i-lucide-phone', hangup: 'i-lucide-phone-off', handoff: 'i-lucide-user-round-plus', check: 'i-lucide-check',
  x: 'i-lucide-x', person: 'i-lucide-user-round', people: 'i-lucide-users-round', look: 'i-lucide-search',
  urgent: 'i-lucide-triangle-alert', wind: 'i-lucide-wind', hail: 'i-lucide-cloud-hail', car: 'i-lucide-car',
  home: 'i-lucide-house', drop: 'i-lucide-droplet', fire: 'i-lucide-flame', key: 'i-lucide-key-round',
  camera: 'i-lucide-camera', lock: 'i-lucide-lock', mic: 'i-lucide-mic', micoff: 'i-lucide-mic-off',
  keys: 'i-lucide-keyboard', lang: 'i-lucide-languages', captions: 'i-lucide-captions', sun: 'i-lucide-sun',
  moon: 'i-lucide-moon', left: 'i-lucide-chevron-left', right: 'i-lucide-chevron-right', down: 'i-lucide-chevron-down',
  shield: 'i-lucide-shield-check', card: 'i-lucide-credit-card', clock: 'i-lucide-clock', waves: 'i-lucide-audio-lines',
  scale: 'i-lucide-scale', doc: 'i-lucide-file-text', swap: 'i-lucide-arrow-left-right', plus: 'i-lucide-plus',
  flag: 'i-lucide-flag', heart: 'i-lucide-heart', sliders: 'i-lucide-sliders-horizontal', pin: 'i-lucide-map-pin',
  send: 'i-lucide-send', upload: 'i-lucide-upload', download: 'i-lucide-download', search: 'i-lucide-search',
  link: 'i-lucide-link', dots: 'i-lucide-ellipsis', volume: 'i-lucide-volume-2', mute: 'i-lucide-volume-x',
  refresh: 'i-lucide-refresh-cw', exit: 'i-lucide-log-out', chain: 'i-lucide-link-2', board: 'i-lucide-list-checks',
  next: 'i-lucide-phone-incoming', find: 'i-lucide-search', hand: 'i-lucide-hand',
}

/** Nuxt UI icon name for a ClaimVoice icon key (unknown keys fall back to a dot, never to nothing). */
export function icon(name: string | null | undefined): string {
  return (name && ICON[name]) || 'i-lucide-dot'
}
