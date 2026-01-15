<script setup lang="ts">
// The app shell (DESIGN.md §3): no bar, no sidebar, no dock and no side column. Each page opens with its question
// (PageHead), which is the navigation; the Bell sits at the top right for people who watch the lines; the
// Questions sheet drops from any heading. Keyboard: M, / or ⌘K open the sheet (/ with Find focused); G then L, C,
// Q, R, S or A go straight to a place.
import { placesFor } from '~/utils/places'

const router = useRouter()
const listening = useListening()
const toast = useToast()
const sheet = useSheet()
const { permissions } = useSession()
let lastG = 0

// The listening composable keeps a plain message (it runs outside components); show each one as a toast.
watch(listening.message, (m) => {
  if (m) toast.add({ id: `cv-${Date.now()}`, title: m, icon: 'i-lucide-message-circle' })
})

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); sheet.show(true); return }
  if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  const k = e.key.toLowerCase()
  if (k === '/') { e.preventDefault(); sheet.show(true); return }
  if (k === 'm' && !sheet.open.value) { e.preventDefault(); sheet.show(); return }
  if (k === 'g') { lastG = Date.now(); return }
  if (Date.now() - lastG < 1200) {
    const to = placesFor(permissions.value).find(p => p.key2?.toLowerCase() === k)?.to
    if (to) { e.preventDefault(); lastG = 0; void router.push(to) }
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="shell">
    <a class="skip" href="#main">Skip to content</a>
    <div class="belt" data-shell>
      <CallBell />
    </div>
    <main id="main" tabindex="-1" class="page">
      <slot />
    </main>
    <QuestionsSheet />
    <TakeOverSheet />
    <HandoffSheet />
  </div>
</template>

<style scoped>
.shell { min-height: 100dvh; position: relative; }
/* The Bell rides at the top right of the page column, above the page (which leaves room for it). */
.belt { position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: min(1280px, 100%); padding: 22px 40px 0; display: flex; justify-content: flex-end; pointer-events: none; z-index: 20; }
.belt > * { pointer-events: auto; }
.page:focus { outline: none; }
.skip { position: absolute; left: 16px; top: -60px; z-index: 70; background: var(--cv-ink); color: var(--cv-bg); padding: 10px 16px; border-radius: 14px; font-weight: 600; text-decoration: none; }
.skip:focus { top: 12px; }
@media (max-width: 720px) {
  .belt { padding: 14px 14px 0; }
}
</style>
