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
      <CvMark :size="88" />
      <h1>{{ notFound ? 'Hmm, nobody\'s on this line.' : 'Something went quiet.' }}</h1>
      <p>{{ notFound ? 'The page you asked for isn\'t here. It may have moved, or the link was mistyped.' : 'We hit a problem showing this page. Calls carry on; ClaimVoice keeps taking them.' }}</p>
      <div class="acts">
        <UButton size="xl" trailing-icon="i-lucide-arrow-right" @click="back">
          Back to ClaimVoice
        </UButton>
        <UButton to="/lines" size="xl" color="neutral" variant="soft" icon="i-lucide-audio-lines">
          Who's on the line?
        </UButton>
      </div>
    </main>
  </div>
</template>

<style scoped>
.err { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr; background: var(--cv-bg); }
.top { display: flex; align-items: center; padding: 18px 40px; }
main { display: grid; justify-items: center; align-content: start; text-align: center; gap: 16px; padding: 64px 24px; }
h1 { font-size: 60px; font-weight: 900; letter-spacing: -0.03em; line-height: 1; max-width: 14ch; }
p { color: var(--cv-muted); font-size: 17px; max-width: 560px; margin: 0; }
.acts { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; margin-top: 10px; }
@media (max-width: 720px) {
  .top { padding: 14px 16px; }
  main { padding: 40px 16px; }
  h1 { font-size: 38px; }
}
</style>
