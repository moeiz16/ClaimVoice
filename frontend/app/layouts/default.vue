<script setup lang="ts">
// The app shell: the work area on the left, the key bank docked to the right edge (DESIGN.md §0.2). No top bar, no
// sidebar, no floating dock. Every page starts with its slate. Keyboard: G L board, G C claims, G Q quality,
// G R routing checks, G S settings; / or ⌘K opens Find.
const router = useRouter()
const listening = useListening()
const toast = useToast()
const findOpen = ref(false)
let lastG = 0

// The listening composable keeps a plain message (it runs outside components); show each one as a toast.
watch(listening.message, (m) => {
  if (m) toast.add({ id: `cv-${Date.now()}`, title: m, icon: 'i-lucide-audio-lines' })
})

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); findOpen.value = true; return }
  if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  const k = e.key.toLowerCase()
  if (k === '/') { e.preventDefault(); findOpen.value = true; return }
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
  <div class="shell">
    <a class="skip" href="#main">Skip to content</a>
    <KeyBank v-model:find="findOpen" />
    <main id="main" tabindex="-1" class="work">
      <slot />
    </main>
    <FindPalette v-model:open="findOpen" />
    <TakeOverSheet />
    <HandoffSheet />
  </div>
</template>

<style scoped>
.shell { min-height: 100dvh; }
.work { min-height: 100dvh; margin-right: 96px; padding-bottom: 48px; min-width: 0; }
.work:focus { outline: none; }
.skip { position: absolute; left: 16px; top: -60px; z-index: 70; background: var(--cv-ink); color: var(--cv-bg); padding: 10px 16px; border-radius: 8px; font-weight: 650; text-decoration: none; }
.skip:focus { top: 12px; }
@media (max-width: 720px) {
  .work { margin-right: 0; min-height: calc(100dvh - 60px); }
}
</style>
