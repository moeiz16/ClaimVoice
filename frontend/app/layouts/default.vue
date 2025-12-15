<script setup lang="ts">
// The app shell: a plain page with the floating dock. No sidebar, no top tab bar, no command palette.
// Keyboard: G L Lines, G C Claims, G Q Quality, G R Routing checks.
const router = useRouter()
let lastG = 0

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  const k = e.key.toLowerCase()
  if (k === 'g') { lastG = Date.now(); return }
  if (Date.now() - lastG < 1200) {
    const to = ({ l: '/lines', c: '/claims', q: '/quality', r: '/routing', s: '/settings' } as Record<string, string>)[k]
    if (to) { e.preventDefault(); lastG = 0; void router.push(to) }
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="app">
    <a class="skip" href="#main">Skip to content</a>
    <main id="main" tabindex="-1">
      <slot />
    </main>
    <AppDock />
    <TakeOverSheet />
    <HandoffSheet />
  </div>
</template>

<style scoped>
.app { min-height: 100dvh; padding-bottom: 110px; }
main:focus { outline: none; }
.skip { position: absolute; left: 16px; top: -60px; z-index: 70; background: var(--cv-ink); color: var(--cv-bg); padding: 10px 16px; border-radius: 999px; font-weight: 650; text-decoration: none; }
.skip:focus { top: 12px; }
@media (max-width: 720px) { .app { padding-bottom: 170px; } }
</style>
