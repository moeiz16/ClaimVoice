// Nuxt UI theme for ClaimVoice, "Ask and answer" (DESIGN.md §7). Semantic colours point at palettes built around the
// sea-glass tokens (main.css @theme); the exact token values are pinned again as CSS variables in main.css. The
// components are re-shaped so they don't read as stock Nuxt UI: 16 px pebbles for controls, 24/32 px for bubbles and
// sheets, 2 px borders, a 3 px pressable lip on solid buttons, a 3 px jade focus ring 3 px out. Soft and subtle
// variants use the AA wash + ink pairs. Status always ships with an icon and a word, never colour alone.
const SOFT: Record<string, string> = {
  primary: 'bg-jade-wash text-jade-ink',
  secondary: 'bg-sand text-caller',
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
  { color, variant: 'subtle' as const, class: `${cls} ring-2 ring-inset ring-current/25` },
])
const softAlert = () => pairs.flatMap(([color, cls]) => [
  { color, variant: 'soft' as const, class: { root: cls } },
  { color, variant: 'subtle' as const, class: { root: `${cls} ring-2 ring-inset ring-current/20` } },
])
// Solid fills with their pressable lip: a darker inset bottom edge that shortens when pressed.
const LIP = 'shadow-[inset_0_-3px_0_var(--cv-lip)] active:shadow-[inset_0_-1px_0_var(--cv-lip)] active:translate-y-[2px]'
const solid = (color: Color, cls: string) => ({ color, variant: 'solid' as const, class: `${cls} ${LIP}` })

export default defineAppConfig({
  ui: {
    colors: {
      primary: 'jade',
      secondary: 'driftwood',
      success: 'jade',
      info: 'harbour',
      warning: 'ochre',
      error: 'coral',
      neutral: 'sea',
    },
    icons: {
      chevronDown: 'i-lucide-chevron-down',
    },
    button: {
      slots: {
        base: 'rounded-[16px] font-medium transition-[transform,box-shadow,background-color,color] duration-150 focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-jade',
      },
      variants: {
        size: {
          xs: { base: 'h-8 px-3 text-[13px] gap-1.5 rounded-[12px]' },
          sm: { base: 'h-10 px-3.5 text-[14px] gap-1.5 rounded-[14px]' },
          md: { base: 'h-11 px-4 text-[14.5px] gap-2' },
          lg: { base: 'h-12 px-5 text-[15px] gap-2' },
          xl: { base: 'h-14 px-6 text-[16px] gap-2.5 rounded-[18px]' },
        },
      },
      compoundVariants: [
        ...soft(),
        solid('primary', 'bg-jade text-on-jade hover:bg-jade/92 disabled:bg-jade/60 aria-disabled:bg-jade/60 focus-visible:outline-ink'),
        solid('neutral', 'bg-ink text-bg hover:bg-ink/90 disabled:bg-ink/50 aria-disabled:bg-ink/50'),
        solid('info', 'bg-person text-white dark:text-[#0B1730] hover:bg-person/92'),
        solid('error', 'bg-urgent text-white dark:text-[#2A0E07] hover:bg-urgent/92'),
        solid('warning', 'bg-siu text-white dark:text-[#2A1C03] hover:bg-siu/92'),
        { color: 'neutral', variant: 'soft', class: 'hover:bg-sunk-2 active:bg-sunk-2' },
        { color: 'primary', variant: 'soft', class: 'hover:bg-seaglass/70' },
        { color: 'neutral', variant: 'outline', class: 'ring-2 ring-inset ring-rule bg-surface hover:bg-sunk text-ink' },
        { color: 'primary', variant: 'outline', class: 'ring-2 ring-inset ring-jade text-jade-ink hover:bg-jade-wash' },
        { color: 'info', variant: 'outline', class: 'ring-2 ring-inset ring-person text-person hover:bg-person-wash' },
        { color: 'primary', variant: 'link', class: 'text-jade-ink hover:text-jade-ink underline-offset-4 hover:underline decoration-2 px-0' },
        { color: 'primary', variant: 'ghost', class: 'text-jade-ink hover:bg-jade-wash' },
        { color: 'neutral', variant: 'ghost', class: 'hover:bg-sunk' },
      ],
      defaultVariants: { size: 'lg' },
    },
    badge: {
      slots: { base: 'font-medium rounded-full gap-1.5' },
      variants: {
        size: {
          md: { base: 'h-7 px-2.5 text-[12.5px]' },
          lg: { base: 'h-8 px-3 text-[13px]' },
          xl: { base: 'h-10 px-4 text-[14.5px]' },
        },
      },
      compoundVariants: soft(),
      defaultVariants: { variant: 'soft', color: 'neutral', size: 'lg' },
    },
    input: {
      slots: { base: 'rounded-[16px] ring-2 ring-inset ring-rule focus-visible:ring-jade bg-surface placeholder:text-muted/80' },
      variants: {
        size: {
          md: { base: 'h-11 px-3.5 text-[14.5px]' },
          lg: { base: 'h-12 px-4 text-[15px]' },
          xl: { base: 'h-14 px-5 text-[16px]' },
        },
      },
      defaultVariants: { size: 'lg' },
    },
    textarea: {
      slots: { base: 'rounded-[16px] ring-2 ring-inset ring-rule focus-visible:ring-jade bg-surface px-4 py-3 text-[15px]' },
    },
    select: {
      slots: { base: 'rounded-[16px] ring-2 ring-inset ring-rule focus-visible:ring-jade bg-surface h-12 text-[15px]', content: 'rounded-[20px] ring-0 shadow-float', item: 'rounded-[12px]' },
    },
    selectMenu: {
      slots: { base: 'rounded-[16px] ring-2 ring-inset ring-rule focus-visible:ring-jade bg-surface h-12 text-[15px]', content: 'rounded-[20px] ring-0 shadow-float', item: 'rounded-[12px]' },
    },
    alert: {
      slots: { root: 'rounded-[20px] p-4 gap-3', title: 'font-semibold text-[15px]', description: 'opacity-100 text-[14px]', icon: 'size-5' },
      compoundVariants: softAlert(),
    },
    tabs: {
      slots: { list: 'rounded-full p-1 bg-sunk', trigger: 'rounded-full font-medium data-[state=active]:text-ink', indicator: 'rounded-full bg-surface shadow-soft' },
    },
    modal: {
      slots: {
        overlay: 'bg-[color-mix(in_srgb,var(--cv-ink)_38%,transparent)] backdrop-blur-[2px]',
        content: 'ring-0 shadow-float rounded-[32px] bg-surface divide-y-0',
        header: 'px-6 pt-6 pb-2 sm:px-7',
        body: 'px-6 sm:px-7 py-3',
        footer: 'px-6 sm:px-7 pb-6 pt-3',
        title: 'font-round text-[26px] leading-tight font-[850] tracking-[-0.015em]',
        description: 'text-[14px] text-muted mt-1',
      },
    },
    slideover: {
      slots: {
        overlay: 'bg-[color-mix(in_srgb,var(--cv-ink)_30%,transparent)]',
        content: 'ring-0 shadow-float bg-surface divide-y-0 data-[side=right]:rounded-l-[32px] data-[side=left]:rounded-r-[32px]',
        header: 'px-6 pt-6 pb-3',
        title: 'font-round text-[24px] leading-tight font-[850] tracking-[-0.015em]',
        description: 'text-[14px] text-muted',
      },
    },
    popover: {
      slots: { content: 'rounded-[24px] ring-0 shadow-float bg-surface' },
    },
    dropdownMenu: {
      slots: { content: 'rounded-[20px] ring-0 shadow-float bg-surface p-1.5', item: 'rounded-[12px] py-2', label: 'text-[13px]' },
    },
    table: {
      slots: {
        root: 'overflow-x-auto',
        base: 'border-separate border-spacing-y-1.5 min-w-full',
        thead: 'bg-transparent',
        tbody: 'divide-y-0',
        th: 'text-[13px] font-medium text-muted py-2 px-4 first:pl-5',
        td: 'text-[14px] text-ink py-3.5 px-4 bg-surface first:rounded-l-[18px] last:rounded-r-[18px] first:pl-5 last:pr-5 tabular-nums whitespace-nowrap',
        tr: 'data-[selectable=true]:hover:[&>td]:bg-jade-wash/50 data-[selected=true]:[&>td]:bg-jade-wash',
        separator: 'hidden',
        empty: 'text-muted py-10',
      },
    },
    tooltip: {
      slots: { content: 'bg-ink text-bg ring-0 rounded-[12px] text-[13px] h-auto py-1.5 px-3 shadow-lift', text: 'whitespace-normal' },
    },
    toast: {
      slots: { root: 'bg-ink ring-0 rounded-[20px] shadow-float', title: 'text-bg font-medium', description: 'text-bg/80', icon: 'text-seaglass' },
    },
    switch: {
      slots: { base: 'focus-visible:outline-3 focus-visible:outline-offset-3' },
    },
    radioGroup: {
      slots: { item: 'rounded-[18px]' },
    },
    accordion: {
      slots: { trigger: 'font-medium text-[15px]' },
    },
    pagination: {
      slots: { list: 'gap-1.5' },
    },
    formField: {
      slots: { label: 'font-medium text-[14px]', help: 'text-[13px]', error: 'text-[13px] font-medium' },
    },
    avatar: {
      slots: { root: 'font-round font-[850]' },
    },
    kbd: {
      base: 'rounded-[8px] font-sans',
    },
  },
})
