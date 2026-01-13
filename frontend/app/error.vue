<script setup lang="ts">
// Not found and unexpected errors, in the product's own voice: the mark, a flat line that breathes, plain words, a
// way back. Left-aligned like every slate.
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const notFound = computed(() => props.error.statusCode === 404)
useHead({ title: notFound.value ? 'Not found · ClaimVoice' : 'Something went wrong · ClaimVoice' })
const back = () => clearError({ redirect: '/' })
</script>

<template>
  <div class="err">
    <header class="top">
      <CvLogo />
    </header>
    <main>
      <div class="slate">
        <h1>{{ notFound ? 'This line isn\'t connected.' : 'Something went quiet.' }}</h1>
        <p>{{ notFound ? 'The page you asked for isn\'t here. It may have moved, or the link was mistyped.' : 'We hit a problem showing this page. Calls carry on; ClaimVoice keeps taking them.' }}</p>
      </div>
      <div class="flat" aria-hidden="true" />
      <div class="acts">
        <UButton trailing-icon="i-lucide-arrow-right" @click="back">
          Back to ClaimVoice
        </UButton>
        <UButton to="/lines" color="neutral" variant="soft" icon="i-lucide-list-checks">
          Open the lines
        </UButton>
      </div>
    </main>
  </div>
</template>

<style scoped>
.err { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr; background: var(--cv-bg); }
.top { display: flex; align-items: center; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
main { display: grid; align-content: start; }
.slate { padding: 48px 32px 22px; display: grid; gap: 10px; }
h1 { font-size: 48px; font-weight: 740; letter-spacing: -0.03em; line-height: 1.05; }
p { color: var(--cv-muted); font-size: 17px; max-width: 620px; margin: 0; }
.flat { height: 2px; margin: 18px 32px 30px; border-radius: 2px; background: var(--cv-faint); animation: breathe var(--m-breathe) var(--ease-breath) infinite; }
.acts { display: flex; gap: 12px; flex-wrap: wrap; padding: 0 32px; }
@media (prefers-reduced-motion: reduce) { .flat { animation: none; } }
@media (max-width: 720px) {
  .top { padding: 12px 16px; }
  .slate { padding: 32px 16px 18px; }
  h1 { font-size: 34px; }
  .flat { margin: 14px 16px 24px; }
  .acts { padding: 0 16px; }
}
</style>
