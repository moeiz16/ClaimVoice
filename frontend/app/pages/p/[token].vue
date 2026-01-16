<script setup lang="ts">
// The photo link a caller gets by text. Mobile-first: the mark, a slate with the claim number, then take or pick
// photos, add a word about each, send. Works in the caller's language. No sign-in: the link itself is the key, and
// it expires.
import type { PhotoLinkInfo } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'
import { MAX_BYTES, looksLikePhoto, needsConversion, toJpeg } from '~/utils/photos'
import { fmtDayLong, fmtTime, ORG_ZONE } from '~/utils/format'
import { demoNow } from '~/utils/demoClock'

definePageMeta({ layout: 'public' })
const route = useRoute()
const token = computed(() => String(route.params.token))
const info = ref<PhotoLinkInfo | null>(null)
const state = ref<'loading' | 'ready' | 'expired' | 'missing' | 'error'>('loading')
interface Item { id: number, file: File, url: string, caption: string, status: 'ready' | 'sending' | 'sent' | 'failed', note: string }
const items = ref<Item[]>([])
const sentCount = ref(0)
let seq = 0
const picker = ref<HTMLInputElement | null>(null)

const fr = computed(() => info.value?.language === 'fr')
const T = computed(() => fr.value
  ? { h: 'Vos photos', sub: 'Pour la réclamation', add: 'Prendre ou choisir des photos', tip: 'Prenez-les quand il fait clair et que c\'est sécuritaire. Un plan large, puis de près.', caption: 'Un mot sur cette photo (facultatif)', send: 'Envoyer', sending: 'Envoi…', sent: 'Envoyée', failed: 'Pas envoyée', done: 'Merci. Votre expert peut les voir maintenant.', left: (n: number) => `Encore ${n} possible${n > 1 ? 's' : ''}`, expires: 'Ce lien expire le', forDays: 'Ce lien fonctionne 3 jours après le texto', expired: 'Ce lien a expiré.', expiredBody: 'Rappelez-nous et nous vous en enverrons un nouveau.', missing: 'Ce lien ne fonctionne pas.', privacy: 'La position de vos photos est retirée avant qu\'elles nous parviennent.', remove: 'Retirer' }
  : { h: 'Your photos', sub: 'For claim', add: 'Take or choose photos', tip: 'Take them when it\'s light and safe. One wide shot, then close up.', caption: 'A word about this photo (optional)', send: 'Send', sending: 'Sending…', sent: 'Sent', failed: 'Not sent', done: 'Thank you. Your adjuster can see them now.', left: (n: number) => `${n} more allowed`, expires: 'This link works until', forDays: 'This link works for 3 days from the text', expired: 'This link has expired.', expiredBody: 'Call us back and we\'ll text you a new one.', missing: 'This link doesn\'t work.', privacy: 'Location details are removed from your photos before they reach us.', remove: 'Remove' })
useHead(() => ({ title: `${T.value.h} · ClaimVoice`, htmlAttrs: { lang: fr.value ? 'fr' : 'en' } }))

onMounted(async () => {
  try {
    info.value = await api.photoLinks.get(token.value)
    sentCount.value = info.value.uploaded
    state.value = 'ready'
  }
  catch (e) {
    state.value = e instanceof ApiError ? (e.status === 410 ? 'expired' : e.status === 404 ? 'missing' : 'error') : 'error'
  }
})
const room = computed(() => Math.max(0, (info.value?.maxPhotos ?? 10) - sentCount.value - items.value.filter(i => i.status !== 'sent').length))

async function pick(e: Event) {
  const files = [...((e.target as HTMLInputElement).files ?? [])].slice(0, room.value)
  for (const f of files) {
    let file = f
    try {
      if (!(await looksLikePhoto(f))) throw new Error('not a photo')
      if (needsConversion(f)) file = await toJpeg(f)
    }
    catch { items.value.push({ id: ++seq, file: f, url: '', caption: '', status: 'failed', note: fr.value ? 'Format non pris en charge. Reprenez-la en JPEG.' : 'This photo\'s format isn\'t supported. Try taking it again.' }); continue }
    if (file.size > MAX_BYTES) { items.value.push({ id: ++seq, file, url: '', caption: '', status: 'failed', note: fr.value ? 'Photo trop grande.' : 'This photo is too large.' }); continue }
    items.value.push({ id: ++seq, file, url: URL.createObjectURL(file), caption: '', status: 'ready', note: '' })
  }
  ;(e.target as HTMLInputElement).value = ''
}
let sendingNow = false
async function sendAll() {
  if (sendingNow) return // a double tap sends each photo once
  sendingNow = true
  try { await sendEach() }
  finally { sendingNow = false }
}
async function sendEach() {
  for (const it of items.value.filter(i => i.status === 'ready' || (i.status === 'failed' && i.url))) {
    it.status = 'sending'
    try {
      await api.photoLinks.upload(token.value, it.file, it.caption.trim() || undefined)
      it.status = 'sent'
      sentCount.value++
    }
    catch (e) {
      it.status = 'failed'
      it.note = e instanceof ApiError ? e.message : (fr.value ? 'Réessayez.' : 'Try again.')
    }
  }
}
// The link lasts 72 hours from the text. Show its end only when it reads sensibly in demo time.
const expiryShown = computed(() => {
  if (!info.value) return false
  const ms = Date.parse(info.value.expiresAt) - demoNow().getTime()
  return ms > 0 && ms < 7 * 86_400_000
})
const allSent = computed(() => items.value.length > 0 && items.value.every(i => i.status === 'sent'))
const sending = computed(() => items.value.some(i => i.status === 'sending'))
onBeforeUnmount(() => items.value.forEach(i => i.url && URL.revokeObjectURL(i.url)))
</script>

<template>
  <div class="ppage">
    <header class="top">
      <CvLogo :to="'/'" />
    </header>
    <main>
      <template v-if="state === 'ready' && info">
        <div class="slate">
          <p class="org">
            {{ info.orgName }} · {{ T.sub }} <b class="num">{{ info.claimReference }}</b>
          </p>
          <h1>{{ T.h }}</h1>
          <p class="tip">
            {{ T.tip }}
          </p>
        </div>

        <div class="sec">
          <input ref="picker" type="file" accept="image/*" capture="environment" multiple class="sr-only-cv" tabindex="-1" aria-hidden="true" :disabled="room === 0" @change="pick">
          <button type="button" class="cam" :disabled="room === 0" @click="picker?.click()">
            <span class="cc" aria-hidden="true"><UIcon name="i-lucide-camera" /></span>
            <b class="round">{{ T.add }}</b>
          </button>
          <p class="left">
            {{ T.left(room) }} · <template v-if="expiryShown">
              {{ T.expires }} {{ fmtDayLong(info.expiresAt, ORG_ZONE, fr ? 'fr' : 'en') }}, {{ fmtTime(info.expiresAt, ORG_ZONE, fr ? 'fr' : 'en') }}
            </template><template v-else>
              {{ T.forDays }}
            </template>
          </p>
        </div>

        <ul v-if="items.length" class="list">
          <li v-for="it in items" :key="it.id" :class="it.status">
            <img v-if="it.url" :src="it.url" alt="">
            <span v-else class="noimg"><UIcon name="i-lucide-camera" class="size-6" /></span>
            <div class="meta">
              <UInput v-if="it.status === 'ready'" v-model="it.caption" :placeholder="T.caption" :aria-label="T.caption" size="lg" class="w-full" />
              <span v-else-if="it.caption" class="cap">{{ it.caption }}</span>
              <CvTag v-if="it.status === 'sent'" kind="fast" icon="check">{{ T.sent }}</CvTag>
              <CvTag v-else-if="it.status === 'sending'" kind="plain" icon="upload">{{ T.sending }}</CvTag>
              <span v-else-if="it.status === 'failed'" class="st"><UIcon name="i-lucide-triangle-alert" class="size-4 shrink-0" />{{ T.failed }}. {{ it.note }}</span>
            </div>
            <UButton v-if="it.status === 'ready'" color="neutral" variant="ghost" icon="i-lucide-x" :aria-label="T.remove" @click="items = items.filter(x => x.id !== it.id)" />
          </li>
        </ul>

        <div v-if="items.some(i => i.status === 'ready') || allSent" class="sec">
          <UButton v-if="items.some(i => i.status === 'ready')" size="xl" block icon="i-lucide-upload" :loading="sending" :disabled="sending" @click="sendAll">
            {{ sending ? T.sending : T.send }} ({{ items.filter(i => i.status === 'ready').length }})
          </UButton>
          <UAlert v-if="allSent" color="success" variant="soft" icon="i-lucide-check" :title="T.done" role="status" :ui="{ title: 'font-round text-[19px] font-[850]' }" />
        </div>

        <p class="privacy">
          <UIcon name="i-lucide-lock" class="size-4 shrink-0" />{{ T.privacy }}
        </p>
      </template>
      <div v-else-if="state === 'loading'" class="slate" aria-busy="true">
        <USkeleton class="h-10 w-3/4" /><USkeleton class="h-14 w-full mt-3" />
      </div>
      <div v-else class="slate gone">
        <span class="hatch" aria-hidden="true" />
        <h1>{{ state === 'expired' ? T.expired : T.missing }}</h1>
        <p>{{ state === 'expired' ? T.expiredBody : 'Check the text we sent, or call us back.' }}</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* The photo link (DESIGN.md §3): phone-first, one question, a big round camera button. */
.ppage { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr; justify-items: center; }
.top { display: flex; align-items: center; padding: 14px 16px; width: 100%; max-width: 560px; }
main { width: 100%; max-width: 560px; display: grid; align-content: start; gap: 14px; padding: 0 14px 32px; }
.slate { padding: 22px 20px 20px; border-radius: 28px; background: var(--cv-surface); display: grid; gap: 8px; box-shadow: var(--cv-shadow-soft); }
.org { margin: 0; color: var(--cv-muted); font-size: 14px; }
.org b { color: var(--cv-ink); font-weight: 600; }
h1 { font-size: 36px; font-weight: 900; letter-spacing: -0.025em; line-height: 1.02; }
.tip { margin: 4px 0 0; padding: 12px 16px; border-radius: 6px 22px 22px 22px; background: var(--cv-jade-wash); font-size: 16px; line-height: 1.4; }
.sec { padding: 4px 0; display: grid; gap: 10px; justify-items: center; }
.cam { display: grid; justify-items: center; gap: 10px; border: 0; background: none; color: var(--cv-ink); padding: 8px; border-radius: 28px; }
.cc { width: 112px; height: 112px; border-radius: 50%; display: grid; place-items: center; font-size: 44px; background: var(--cv-jade); color: var(--cv-on-jade); box-shadow: inset 0 -6px 0 var(--cv-lip); transition: transform 160ms var(--ease-spring); }
.cam:active .cc { transform: translateY(2px); }
.cam:disabled { opacity: .5; }
.cam b { font-size: 20px; font-weight: 900; }
.left { margin: 0; color: var(--cv-muted); font-size: 13px; text-align: center; }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.list li { display: grid; grid-template-columns: 72px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px; border-radius: 22px; background: var(--cv-surface); }
.list img, .noimg { width: 72px; height: 72px; border-radius: 16px; object-fit: cover; display: grid; place-items: center; background: var(--cv-sunk); color: var(--cv-faint); }
.meta { display: grid; gap: 6px; min-width: 0; justify-items: start; }
.cap { font-weight: 500; font-size: 14px; }
.st { display: flex; gap: 6px; align-items: flex-start; font-size: 13px; font-weight: 500; color: var(--cv-urgent); }
.privacy { margin: 0; padding: 6px 6px 0; display: flex; gap: 6px; align-items: flex-start; color: var(--cv-muted); font-size: 13px; }
.gone { padding-top: 26px; }
.gone p { margin: 0; color: var(--cv-muted); font-size: 16px; }
.hatch { width: 100%; height: 56px; border-radius: 999px; background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); }
.sec :deep(button[data-slot="base"]), .sec > :deep(.w-full) { width: 100%; }
</style>
