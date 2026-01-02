<script setup lang="ts">
// The photo link a caller gets by text. Mobile-first: take or pick photos, add a word about each, send. Works in
// the caller's language. No sign-in: the link itself is the key, and it expires.
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
  <div class="page">
    <header><CvLogo :to="'/'" /></header>
    <main>
      <template v-if="state === 'ready' && info">
        <p class="org">
          {{ info.orgName }} · {{ T.sub }} <b class="num">{{ info.claimReference }}</b>
        </p>
        <h1>{{ T.h }}</h1>
        <p class="tip">
          {{ T.tip }}
        </p>
        <label class="btn primary big" :class="{ off: room === 0 }">
          <CvIcon name="camera" />{{ T.add }}
          <input type="file" accept="image/*" capture="environment" multiple class="sr-only-cv" :disabled="room === 0" @change="pick">
        </label>
        <p class="left">
          {{ T.left(room) }} · <template v-if="expiryShown">
            {{ T.expires }} {{ fmtDayLong(info.expiresAt, ORG_ZONE, fr ? 'fr' : 'en') }}, {{ fmtTime(info.expiresAt, ORG_ZONE, fr ? 'fr' : 'en') }}
          </template><template v-else>
            {{ T.forDays }}
          </template>
        </p>
        <ul class="list">
          <li v-for="it in items" :key="it.id" :class="it.status">
            <img v-if="it.url" :src="it.url" alt="">
            <span v-else class="noimg"><CvIcon name="camera" /></span>
            <div class="meta">
              <input v-if="it.status === 'ready'" v-model="it.caption" class="field-input sm" :placeholder="T.caption" :aria-label="T.caption">
              <span v-else-if="it.caption" class="cap">{{ it.caption }}</span>
              <span class="st">
                <CvIcon :name="it.status === 'sent' ? 'check' : it.status === 'failed' ? 'urgent' : it.status === 'sending' ? 'upload' : 'camera'" size="s" />
                {{ it.status === 'sent' ? T.sent : it.status === 'failed' ? `${T.failed}. ${it.note}` : it.status === 'sending' ? T.sending : '' }}
              </span>
            </div>
            <button v-if="it.status === 'ready'" type="button" class="iconbtn" :aria-label="T.remove" @click="items = items.filter(x => x.id !== it.id)">
              <CvIcon name="x" />
            </button>
          </li>
        </ul>
        <button v-if="items.some(i => i.status === 'ready')" class="btn primary big" type="button" :disabled="sending" @click="sendAll">
          <CvIcon name="upload" />{{ sending ? T.sending : T.send }} ({{ items.filter(i => i.status === 'ready').length }})
        </button>
        <p v-if="allSent" class="done" role="status">
          <CvIcon name="check" />{{ T.done }}
        </p>
        <p class="privacy">
          <CvIcon name="lock" size="s" />{{ T.privacy }}
        </p>
      </template>
      <div v-else-if="state === 'loading'" class="load" aria-busy="true">
        <span class="skeleton" style="height: 40px; width: 70%" /><span class="skeleton" style="height: 56px" />
      </div>
      <div v-else class="gone">
        <span class="hatch" aria-hidden="true" />
        <h1>{{ state === 'expired' ? T.expired : T.missing }}</h1>
        <p>{{ state === 'expired' ? T.expiredBody : 'Check the text we sent, or call us back.' }}</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.page { min-height: 100dvh; display: grid; grid-template-rows: 64px 1fr; }
header { display: flex; align-items: center; padding: 0 16px; }
main { width: 100%; max-width: 520px; margin: 0 auto; padding: 8px 16px 40px; display: grid; gap: 12px; align-content: start; }
.org { margin: 0; color: var(--cv-muted); font-size: 14px; }
h1 { font-size: 40px; font-weight: 750; letter-spacing: -0.04em; line-height: 1.05; }
.tip { margin: 0; font-family: var(--font-display); font-size: 19px; font-weight: 550; color: var(--cv-caller); line-height: 1.3; }
.big { height: 56px; font-size: 16px; width: 100%; cursor: pointer; }
.big.off { opacity: .5; pointer-events: none; }
.left { margin: 0; color: var(--cv-muted); font-size: 13px; text-align: center; }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.list li { display: grid; grid-template-columns: 72px 1fr auto; gap: 10px; align-items: center; background: var(--cv-surface); border-radius: 20px; padding: 8px; }
.list img, .noimg { width: 72px; height: 72px; border-radius: 14px; object-fit: cover; display: grid; place-items: center; background: var(--cv-sunk); color: var(--cv-faint); }
.meta { display: grid; gap: 4px; min-width: 0; }
.cap { font-weight: 600; font-size: 14px; }
.st { display: flex; gap: 4px; align-items: center; font-size: 13px; font-weight: 650; color: var(--cv-muted); }
.sent .st { color: var(--cv-fast); } .failed .st { color: var(--cv-urgent); }
.done { margin: 0; display: flex; gap: 8px; align-items: center; font-family: var(--font-display); font-size: 20px; font-weight: 650; color: var(--cv-fast); }
.privacy { margin: 8px 0 0; display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-size: 13px; }
.load { display: grid; gap: 12px; }
.gone { display: grid; gap: 10px; padding-top: 40px; }
.gone p { margin: 0; color: var(--cv-muted); font-size: 16px; }
.hatch { width: 100%; height: 56px; border-radius: 20px; background: repeating-linear-gradient(-45deg, var(--cv-sunk-2) 0 5px, var(--cv-sunk) 5px 10px); }
</style>
