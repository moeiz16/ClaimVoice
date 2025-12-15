<script setup lang="ts">
// A bottom sheet dialog (Take over, Change route, Hand off, Review and sign off): focus trapped while open, Escape
// closes, focus returns to the opener. Hand motion: rises from below; reduced motion crossfades.
const props = withDefaults(defineProps<{ open: boolean, title: string, wide?: boolean }>(), { wide: false })
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
let opener: Element | null = null
const titleId = useId()

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

watch(() => props.open, async (open) => {
  if (open) {
    opener = document.activeElement
    await nextTick()
    const first = panel.value?.querySelector<HTMLElement>('[autofocus]') ?? panel.value?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
  }
  else if (opener instanceof HTMLElement) opener.focus()
})

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.stopPropagation(); emit('close'); return }
  if (e.key !== 'Tab' || !panel.value) return
  const items = [...panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(el => el.offsetParent !== null)
  if (!items.length) return
  const first = items[0]!
  const last = items[items.length - 1]!
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="scrim" @click.self="emit('close')" @keydown="onKey">
        <section ref="panel" class="sheet" :class="{ wide }" role="dialog" aria-modal="true" :aria-labelledby="titleId">
          <div class="grab" aria-hidden="true" />
          <header>
            <h2 :id="titleId">
              {{ title }}
            </h2>
            <button class="iconbtn" type="button" aria-label="Close" @click="emit('close')">
              <CvIcon name="x" />
            </button>
          </header>
          <slot />
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; z-index: 60; background: color-mix(in srgb, var(--cv-dock) 38%, transparent); display: flex; align-items: flex-end; justify-content: center; padding: 16px; }
.sheet { width: 100%; max-width: 560px; background: var(--cv-surface); border-radius: 28px; padding: 10px 24px 24px; box-shadow: var(--cv-shadow-float); max-height: calc(100dvh - 32px); overflow: auto; margin-bottom: 96px; }
.sheet.wide { max-width: 720px; }
.grab { width: 44px; height: 5px; border-radius: 3px; background: var(--cv-sunk-2); margin: 0 auto 10px; }
header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
h2 { font-size: 24px; font-weight: 700; letter-spacing: -0.025em; flex: 1; }
.sheet-enter-active, .sheet-leave-active { transition: opacity 220ms var(--ease-voice); }
.sheet-enter-active .sheet, .sheet-leave-active .sheet { transition: transform 480ms var(--ease-lift); }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .sheet, .sheet-leave-to .sheet { transform: translateY(40px); }
@media (max-width: 720px) {
  .scrim { padding: 0; }
  .sheet { border-radius: 22px 22px 0 0; margin-bottom: 0; padding: 10px 16px 24px; }
}
</style>
