<script setup lang="ts">
// The dock: a floating aubergine pill, the app's only navigation (Lines · Claims · Quality · Routing checks ·
// Settings), which also carries the line you are on. On a phone it becomes a bottom sheet with icon tabs and the
// mini player above them.
import { api } from '~/utils/api'
import { firstName } from '~/utils/format'

const route = useRoute()
const { permissions, can } = useSession()
const nav = computed(() => navFor(permissions.value))
const { waiting } = useSwitchboard(can('lines:read'))
const listening = useListening()
const { onLine, whisperOpen, message } = listening
const clock = useDemoClock()
const toReview = ref(0)

onMounted(async () => {
  if (!can('qa:read')) return
  try { toReview.value = (await api.qa.queue({ status: 'needs_review', pageSize: 1 })).total }
  catch { /* the badge is optional */ }
})

const items = computed(() => [
  { key: 'lines', to: '/lines', label: 'Lines', short: 'Lines', icon: 'waves', show: nav.value.lines, count: waiting.value, countLabel: 'waiting for a person' },
  { key: 'claims', to: '/claims', label: 'Claims', short: 'Claims', icon: 'doc', show: nav.value.claims, count: 0, countLabel: '' },
  { key: 'quality', to: '/quality', label: 'Quality', short: 'Quality', icon: 'flag', show: nav.value.quality, count: toReview.value, countLabel: 'calls to review' },
  { key: 'routing', to: '/routing', label: 'Routing checks', short: 'Routing', icon: 'scale', show: nav.value.routing, count: 0, countLabel: '' },
  { key: 'settings', to: '/settings', label: 'Settings', short: 'Settings', icon: 'sliders', show: nav.value.settings, count: 0, countLabel: '' },
].filter(i => i.show))

const isCurrent = (to: string) => route.path === to || route.path.startsWith(`${to}/`)

const whisperText = ref('')
const whisperInput = ref<HTMLInputElement | null>(null)
watch(whisperOpen, async (o) => { if (o) { await nextTick(); whisperInput.value?.focus() } })
async function sendWhisper() {
  if (!onLine.value || !whisperText.value.trim()) return
  if (await listening.whisper(onLine.value.callId, whisperText.value.trim())) {
    whisperText.value = ''
    whisperOpen.value = false
  }
}

const tookOver = computed(() => onLine.value?.mode === 'took_over')
</script>

<template>
  <div class="dock-wrap no-print">
    <div v-if="message" class="toast" role="status">
      {{ message }}
    </div>
    <form v-if="whisperOpen && onLine" class="whisper-pop" @submit.prevent="sendWhisper">
      <CvIcon name="whisper" />
      <label class="sr-only-cv" for="dock-whisper">Whisper to ClaimVoice</label>
      <input id="dock-whisper" ref="whisperInput" v-model="whisperText" maxlength="280" :placeholder="`Whisper to ClaimVoice. ${firstName(onLine.callerLabel)} won't hear this.`" @keydown.escape="whisperOpen = false">
      <button class="btn sm primary" type="submit" :disabled="!whisperText.trim()">
        Send
      </button>
    </form>
    <nav class="dock" aria-label="ClaimVoice">
      <NuxtLink class="home" to="/lines" aria-label="ClaimVoice, Lines">
        <CvMark :size="32" />
      </NuxtLink>
      <ul class="nav">
        <li v-for="i in items" :key="i.key">
          <NuxtLink :to="i.to" :aria-current="isCurrent(i.to) ? 'page' : undefined">
            <CvIcon :name="i.icon" class="nav-ic" />
            <span class="lbl"><span class="long">{{ i.label }}</span><span class="short">{{ i.short }}</span></span>
            <span v-if="i.count" class="count num" :aria-label="`${i.count} ${i.countLabel}`">{{ i.count }}</span>
          </NuxtLink>
        </li>
      </ul>
      <template v-if="onLine">
        <span class="sep" aria-hidden="true" />
        <div class="now" role="group" aria-label="The line you are on">
          <span class="live-dot" aria-hidden="true" />
          <NuxtLink class="who" :to="`/lines/${onLine.callId}`">
            <b>{{ onLine.lineLabel }} · {{ onLine.callerLabel }}</b>
            <span v-if="tookOver">You're on the call · ClaimVoice is taking notes</span>
            <span v-else>{{ onLine.language === 'fr' ? 'French · ' : '' }}{{ onLine.place ?? '' }}{{ onLine.place ? ' · ' : '' }}<time class="num">{{ clock.elapsed(onLine.answeredAt) }}</time></span>
          </NuxtLink>
          <div class="wave">
            <LiveWave :seed-key="onLine.callId" palette="dock" :bar="2" :gap="2" />
          </div>
          <button class="ctl on" type="button" aria-pressed="true" :title="tookOver ? 'Leave the call' : 'Stop listening'" @click="listening.stop()">
            <CvIcon name="listen" /><span class="lbl-l">{{ tookOver ? 'On the call' : 'Listening' }}</span>
          </button>
          <button v-if="!tookOver" class="ctl" type="button" :aria-expanded="whisperOpen" @click="whisperOpen = !whisperOpen">
            <CvIcon name="whisper" /><span class="lbl-l">Whisper</span>
          </button>
          <button v-if="!tookOver" class="ctl take" type="button" @click="listening.takeoverFor.value = onLine">
            <CvIcon name="phone" /><span class="lbl-l">Take over</span>
          </button>
          <button v-else class="ctl take" type="button" @click="listening.giveBack(onLine.callId)">
            <CvIcon name="swap" /><span class="lbl-l">Hand back</span>
          </button>
          <button v-if="can('calls:handoff')" class="ctl more" type="button" aria-label="Hand off this call" title="Hand off" @click="listening.handoffFor.value = onLine">
            <CvIcon name="handoff" />
          </button>
        </div>
      </template>
    </nav>
  </div>
</template>

<style scoped>
.dock-wrap { position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); z-index: 40; display: flex; flex-direction: column; align-items: center; gap: 10px; max-width: calc(100vw - 32px); }
.dock { display: flex; align-items: center; gap: 6px; height: 68px; padding: 0 10px 0 14px; border-radius: 999px; background: var(--cv-dock); color: var(--cv-on-dock); box-shadow: var(--cv-shadow-float); max-width: 100%; }
.home { display: grid; place-items: center; width: 40px; height: 40px; margin-right: 6px; border-radius: 50%; }
.nav { display: flex; gap: 2px; list-style: none; margin: 0; padding: 0; }
.nav a { display: inline-flex; align-items: center; gap: 7px; height: 44px; padding: 0 15px; white-space: nowrap; border-radius: 999px; color: var(--cv-dock-muted); text-decoration: none; font-weight: 600; font-size: 14.5px; position: relative; }
.nav a:hover, .nav a[aria-current="page"] { color: var(--cv-on-dock); background: var(--cv-dock-raise); }
.nav a:focus-visible, .ctl:focus-visible, .home:focus-visible, .who:focus-visible { outline-color: var(--cv-dock-orchid); }
.nav-ic, .short { display: none; }
.count { min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px; background: var(--cv-dock-orchid); color: #2A1530; font-size: 11.5px; font-weight: 800; display: grid; place-items: center; }
.sep { width: 1px; height: 32px; background: var(--cv-dock-raise); margin: 0 8px; }
.now { display: flex; align-items: center; gap: 10px; height: 52px; padding: 0 6px 0 14px; border-radius: 999px; background: var(--cv-dock-raise); min-width: 0; }
.who { display: flex; flex-direction: column; line-height: 1.2; min-width: 0; color: inherit; text-decoration: none; border-radius: 10px; }
.who b { font-size: 13.5px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.who span { font-size: 12px; color: var(--cv-dock-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wave { width: 150px; height: 34px; flex: none; }
.ctl { display: inline-flex; align-items: center; gap: 7px; height: 44px; padding: 0 15px 0 12px; border: 0; border-radius: 999px; background: transparent; color: var(--cv-on-dock); font-weight: 650; font-size: 14px; white-space: nowrap; }
.ctl:hover { background: rgba(255, 255, 255, .07); }
.ctl.on { background: var(--cv-dock-orchid); color: #2A1530; }
.ctl.take { background: var(--cv-on-dock); color: var(--cv-dock); }
.ctl.more { padding: 0 10px; }
.toast { background: var(--cv-ink); color: var(--cv-bg); border-radius: 999px; padding: 10px 18px; font-weight: 600; font-size: 14px; box-shadow: var(--cv-shadow-lift); animation: rise-in 260ms var(--ease-voice); }
.whisper-pop { display: flex; align-items: center; gap: 10px; width: min(560px, calc(100vw - 32px)); padding: 6px 6px 6px 16px; border-radius: 999px; background: var(--cv-surface); box-shadow: var(--cv-shadow-float); color: var(--cv-person); animation: rise-in 220ms var(--ease-voice); }
.whisper-pop input { flex: 1; border: 0; background: transparent; font: inherit; font-size: 14.5px; color: var(--cv-ink); min-width: 0; height: 40px; }
.whisper-pop input:focus { outline: none; }
@media (max-width: 1240px) { .wave { width: 90px; } .lbl-l { display: none; } .ctl { padding: 0 11px; } }
@media (max-width: 720px) {
  .dock-wrap { left: 0; right: 0; bottom: 0; transform: none; max-width: none; gap: 8px; }
  .dock { width: 100%; border-radius: 22px 22px 0 0; height: auto; padding: 8px 8px calc(14px + env(safe-area-inset-bottom)); flex-direction: column-reverse; align-items: stretch; gap: 8px; }
  .home, .sep { display: none; }
  .nav { justify-content: space-between; }
  .nav li { flex: 1; }
  .nav a { width: 100%; flex-direction: column; gap: 2px; height: 50px; padding: 4px 0 0; font-size: 11px; justify-content: center; }
  .nav-ic { display: block; }
  .long { display: none; }
  .short { display: inline; }
  .count { position: absolute; top: 2px; left: calc(50% + 6px); min-width: 17px; height: 17px; font-size: 10px; padding: 0 4px; }
  .now { height: 56px; padding: 0 6px 0 12px; gap: 8px; }
  .wave { width: 56px; }
  .who { flex: 1; }
  .ctl.more { display: none; }
}
</style>
