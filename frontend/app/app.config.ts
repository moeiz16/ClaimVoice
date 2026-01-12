// Nuxt UI theme for ClaimVoice. Semantic colours point at palettes built around the pink tokens (main.css @theme);
// the exact token values are pinned again as CSS variables in main.css. Soft and subtle variants are re-pointed at
// the token wash + ink pairs that pass WCAG AA (DESIGN.md §7), since a colour on its own 10 % tint does not
// (orchid on its tint is 4.3 : 1). Status always ships with an icon and a word, never colour alone.
const SOFT: Record<string, string> = {
  primary: 'bg-orchid-wash text-orchid-ink',
  secondary: 'bg-caller-wash text-caller',
  success: 'bg-fast-wash text-fast',
  info: 'bg-adj-wash text-adj',
  warning: 'bg-siu-wash text-siu',
  error: 'bg-urgent-wash text-urgent',
  neutral: 'bg-sunk text-ink',
}
type Color = 'primary' | 'secondary' | 'success' | 'info' | 'warning' | 'error' | 'neutral'
const pairs = Object.entries(SOFT) as [Color, string][]
const soft = () => pairs.flatMap(([color, cls]) => [
  { color, variant: 'soft' as const, class: cls },
  { color, variant: 'subtle' as const, class: `${cls} ring ring-inset ring-current/20` },
])
const softAlert = () => pairs.flatMap(([color, cls]) => [
  { color, variant: 'soft' as const, class: { root: cls } },
  { color, variant: 'subtle' as const, class: { root: `${cls} ring ring-inset ring-current/20` } },
])

export default defineAppConfig({
  ui: {
    colors: {
      primary: 'orchid',
      secondary: 'plum',
      success: 'meadow',
      info: 'cobalt',
      warning: 'ochre',
      error: 'scarlet',
      neutral: 'mauve',
    },
    button: {
      slots: { base: 'font-semibold' },
      compoundVariants: [
        ...soft(),
        { color: 'neutral', variant: 'solid', class: 'bg-ink text-bg hover:bg-ink/90 active:bg-ink/85 disabled:bg-ink aria-disabled:bg-ink' },
        { color: 'neutral', variant: 'soft', class: 'hover:bg-sunk-2 active:bg-sunk-2' },
        { color: 'primary', variant: 'link', class: 'text-orchid-ink hover:text-orchid-ink underline-offset-3 hover:underline' },
        { color: 'primary', variant: 'ghost', class: 'text-orchid-ink' },
      ],
      defaultVariants: { size: 'lg' },
    },
    badge: {
      slots: { base: 'font-semibold rounded-full' },
      compoundVariants: soft(),
      defaultVariants: { variant: 'soft', color: 'neutral', size: 'lg' },
    },
    alert: {
      slots: { root: 'rounded-md', title: 'font-semibold', description: 'opacity-100' },
      compoundVariants: softAlert(),
    },
    tabs: {
      slots: { trigger: 'font-semibold' },
    },
    modal: {
      slots: {
        content: 'ring-0 shadow-[var(--cv-shadow-float)] rounded-lg',
        title: 'font-voice text-xl font-semibold [font-variation-settings:"FLAR"_100]',
      },
    },
    slideover: {
      slots: { title: 'font-voice text-xl font-semibold [font-variation-settings:"FLAR"_100]' },
    },
    table: {
      slots: {
        th: 'text-[12.5px] font-semibold text-muted py-2.5',
        td: 'text-[14px] text-ink py-3 tabular-nums',
        tr: 'data-[selectable=true]:hover:bg-sunk',
      },
    },
    tooltip: {
      slots: { content: 'bg-ink text-bg ring-0 text-[13px] h-auto py-1.5 px-2.5', text: 'whitespace-normal' },
    },
    toast: {
      slots: { root: 'bg-ink ring-0', title: 'text-bg font-semibold', description: 'text-bg/80', icon: 'text-dock-orchid' },
    },
    stepper: {
      slots: { title: 'font-semibold text-[13px]', description: 'text-[12px]' },
    },
  },
})
