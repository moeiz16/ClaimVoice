<script setup lang="ts">
// Not found and unexpected errors, in the product's own voice: a flat line, plain words, a way back.
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const notFound = computed(() => props.error.statusCode === 404)
useHead({ title: notFound.value ? 'Not found · ClaimVoice' : 'Something went wrong · ClaimVoice' })
const back = () => clearError({ redirect: '/' })
</script>

<template>
  <div class="err">
    <header><CvLogo /></header>
    <main>
      <div class="flat" aria-hidden="true" />
      <h1>{{ notFound ? 'This line isn\'t connected.' : 'Something went quiet.' }}</h1>
      <p>{{ notFound ? 'The page you asked for isn\'t here. It may have moved, or the link was mistyped.' : 'We hit a problem showing this page. Calls carry on; ClaimVoice keeps taking them.' }}</p>
      <div class="acts">
        <button class="btn primary" type="button" @click="back">
          Back to ClaimVoice
        </button>
        <NuxtLink class="btn soft" to="/lines">
          Open the lines
        </NuxtLink>
      </div>
    </main>
  </div>
</template>

<style scoped>
.err { min-height: 100dvh; display: grid; grid-template-rows: 76px 1fr; }
header { display: flex; align-items: center; padding: 0 40px; }
main { display: grid; place-content: center; justify-items: center; text-align: center; gap: 16px; padding: 0 16px 80px; }
.flat { width: min(560px, 80vw); height: 2px; border-radius: 2px; background: var(--cv-faint); margin-bottom: 24px; animation: breathe var(--m-breathe) var(--ease-breath) infinite; }
h1 { font-size: 48px; font-weight: 750; letter-spacing: -0.04em; }
p { color: var(--cv-muted); font-size: 17px; max-width: 520px; margin: 0; }
.acts { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
@media (max-width: 720px) { header { padding: 0 16px; } h1 { font-size: 34px; } }
</style>
