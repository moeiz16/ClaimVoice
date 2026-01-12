<script setup lang="ts">
// The key bank (DESIGN.md §0.2): ClaimVoice's navigation, docked to the right edge like the line and feature keys
// beside a desk phone's display. From the top: the mark, a numbered key with a lamp for every live line (in line
// order, so a key keeps its place), NEXT (take the next caller in NEXT order), the feature keys, then Find and the
// avatar. The line you're listening to stays lit wherever you go; its talkback controls open from its key.
// Phones: a key row across the top, with the feature keys in a drawer.
import { api } from '~/utils/api'
import { boardRows, lineKeys, nextCaller } from '~/utils/board'
import { navFor } from '~/composables/useSession'

const route = useRoute()
const { permissions, can } = useSession()
const nav = computed(() => navFor(permissions.value))
const { snapshot } = useSwitchboard(can('lines:read'))
const listening = useListening()
const clock = useDemoClock()
const toReview = ref(0)
const findOpen = defineModel<boolean>('find', { default: false })
const drawer = ref(false)
const talkback = ref(false)

onMounted(async () => {
  if (!can('qa:read')) return
  try { toReview.value = (await api.qa.queue({ status: 'needs_review', pageSize: 1 })).total }
  catch { /* the count is optional */ }
})

const rows = computed(() => (snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []))
const keys = computed(() => lineKeys(rows.value))
const next = computed(() => nextCaller(rows.value))
const waiting = computed(() => rows.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting').length)
const onCall = computed(() => listening.onLine.value?.callId ?? null)
const isCurrent = (to: string) => route.path === to || route.path.startsWith(`${to}/`)

const features = computed(() => [
  { key: 'lines', to: '/lines', label: 'Board', icon: 'i-lucide-list-checks', show: nav.value.lines, count: waiting.value, countLabel: 'waiting for a person' },
  { key: 'claims', to: '/claims', label: 'Claims', icon: 'i-lucide-file-text', show: nav.value.claims, count: 0, countLabel: '' },
  { key: 'quality', to: '/quality', label: 'Quality', icon: 'i-lucide-flag', show: nav.value.quality, count: toReview.value, countLabel: 'calls to review' },
  { key: 'routing', to: '/routing', label: 'Routing', icon: 'i-lucide-scale', show: nav.value.routing, count: 0, countLabel: '' },
  { key: 'settings', to: '/settings', label: 'Settings', icon: 'i-lucide-sliders-horizontal', show: nav.value.settings, count: 0, countLabel: '' },
].filter(f => f.show))

async function takeNext() {
  const r = next.value
  if (!r) return
  if (r.handoff && can('calls:handoff')) {
    const ok = await listening.acceptHandoff(listening.fromLine({ callId: r.callId, lineLabel: r.lineLabel, callerLabel: r.callerLabel, place: r.place, language: r.language, answeredAt: r.since }))
    if (ok) await navigateTo(`/lines/${r.callId}`)
  }
  else await navigateTo(`/lines/${r.callId}`)
}
const nextLabel = computed(() => (next.value ? `Take the next caller: ${next.value.callerLabel}, ${next.value.stateWord.toLowerCase()}, waiting ${clock.elapsed(next.value.since)}` : 'Nobody is waiting for a person'))
watch(() => route.fullPath, () => { drawer.value = false; talkback.value = false })
</script>

<template>
  <nav class="bank" data-keybank aria-label="ClaimVoice keys">
    <NuxtLink class="mark" to="/lines" aria-label="ClaimVoice, the board">
      <CvMark :size="34" />
    </NuxtLink>

    <section v-if="nav.lines" class="lines" aria-label="Lines">
      <span class="cap">Lines</span>
      <ul class="keys">
        <li v-for="r in keys" :key="r.callId">
          <UPopover v-if="onCall === r.callId" v-model:open="talkback" :content="{ side: 'left', align: 'start', sideOffset: 12 }">
            <button type="button" class="lit-wrap" :aria-label="`${r.lineLabel}, ${r.callerLabel}: you are listening. Open the talkback controls.`">
              <LineKey :row="r" listening plain :current="route.path === `/lines/${r.callId}`" />
            </button>
            <template #content>
              <Talkback />
            </template>
          </UPopover>
          <LineKey v-else :row="r" :current="route.path === `/lines/${r.callId}`" />
        </li>
        <li v-if="!keys.length" class="idle">
          All quiet
        </li>
      </ul>
      <UTooltip :text="nextLabel" :content="{ side: 'left' }">
        <button type="button" class="next" :disabled="!next" :aria-label="nextLabel" @click="takeNext">
          <UIcon name="i-lucide-phone-incoming" class="size-5" />
          <span>Next</span>
          <span v-if="waiting" class="count num">{{ waiting }}</span>
        </button>
      </UTooltip>
    </section>

    <ul class="features" aria-label="Go to">
      <li v-for="f in features" :key="f.key">
        <NuxtLink :to="f.to" class="feat" :aria-current="isCurrent(f.to) ? 'page' : undefined" :aria-label="f.count ? `${f.label}, ${f.count} ${f.countLabel}` : f.label">
          <UIcon :name="f.icon" class="size-5" />
          <span>{{ f.label }}</span>
          <span v-if="f.count" class="count num" aria-hidden="true">{{ f.count }}</span>
        </NuxtLink>
      </li>
    </ul>

    <div class="foot">
      <UTooltip text="Find a line, a claim or a page" :kbds="['/']" :content="{ side: 'left' }">
        <button type="button" class="feat find" aria-label="Find" @click="findOpen = true">
          <UIcon name="i-lucide-search" class="size-5" /><span>Find</span>
        </button>
      </UTooltip>
      <AccountMenu side="left" />
    </div>
  </nav>

  <!-- Phones: a key row across the top; the feature keys open in a drawer from the right. -->
  <nav class="row" data-keybank aria-label="ClaimVoice keys">
    <NuxtLink class="mark" to="/lines" aria-label="ClaimVoice, the board">
      <CvMark :size="28" />
    </NuxtLink>
    <ul v-if="nav.lines" class="rkeys" aria-label="Lines">
      <li v-for="r in keys" :key="r.callId">
        <LineKey :row="r" :listening="onCall === r.callId" :current="route.path === `/lines/${r.callId}`" row2 />
      </li>
    </ul>
    <UDrawer v-model:open="drawer" direction="right" title="Keys" description="Where to go, and your account" :ui="{ content: 'w-[300px] bg-dock text-on-dock', title: 'text-on-dock', description: 'text-dock-muted' }">
      <button type="button" class="menu" :aria-label="waiting ? `Keys, ${waiting} waiting for a person` : 'Keys'">
        <UIcon name="i-lucide-menu" class="size-6" />
        <span v-if="waiting" class="count num" aria-hidden="true">{{ waiting }}</span>
      </button>
      <template #body>
        <div class="drawer">
          <button v-if="nav.lines" type="button" class="next wide" :disabled="!next" @click="takeNext">
            <UIcon name="i-lucide-phone-incoming" class="size-5" /><span>{{ next ? `Next: ${next.callerLabel}` : 'Nobody waiting' }}</span>
          </button>
          <NuxtLink v-for="f in features" :key="f.key" :to="f.to" class="feat wide" :aria-current="isCurrent(f.to) ? 'page' : undefined">
            <UIcon :name="f.icon" class="size-5" /><span>{{ f.label }}</span>
            <span v-if="f.count" class="count num">{{ f.count }}</span>
          </NuxtLink>
          <button type="button" class="feat wide" @click="drawer = false; findOpen = true">
            <UIcon name="i-lucide-search" class="size-5" /><span>Find</span>
          </button>
          <div class="acctrow">
            <AccountMenu side="top" />
          </div>
        </div>
      </template>
    </UDrawer>
  </nav>
</template>

<style scoped>
.bank {
  position: fixed; top: 0; right: 0; bottom: 0; width: 96px; z-index: 40; display: flex; flex-direction: column;
  align-items: center; gap: 14px; padding: 16px 0 14px; background: var(--cv-dock); color: var(--cv-on-dock);
  overflow-y: auto; scrollbar-width: none;
}
.mark { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 14px; }
.mark:focus-visible, .feat:focus-visible, .next:focus-visible, .lit-wrap:focus-visible, .menu:focus-visible { outline: 3px solid var(--cv-dock-orchid); outline-offset: 2px; }
.lines { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 100%; padding: 12px 0 14px; border-top: 1px solid rgba(255, 255, 255, .1); border-bottom: 1px solid rgba(255, 255, 255, .1); }
.cap { font-size: 11px; font-weight: 650; color: var(--cv-dock-muted); }
.keys { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.idle { font-size: 11.5px; color: var(--cv-dock-muted); text-align: center; width: 64px; }
.lit-wrap { border: 0; background: none; padding: 0; border-radius: 10px; }
.next {
  position: relative; width: 64px; height: 50px; border: 0; border-radius: 10px; display: grid; place-items: center; gap: 0;
  align-content: center; background: var(--cv-on-dock); color: var(--cv-dock); font-weight: 700; font-size: 12px;
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, .2);
}
.next:disabled { background: transparent; color: var(--cv-dock-muted); box-shadow: inset 0 0 0 1.5px rgba(255, 255, 255, .14); cursor: default; }
.features { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.feat {
  position: relative; width: 76px; min-height: 54px; display: grid; place-items: center; align-content: center; gap: 3px;
  border: 0; border-radius: 10px; background: transparent; color: var(--cv-dock-muted); text-decoration: none;
  font-size: 12px; font-weight: 600;
}
.feat:hover { color: var(--cv-on-dock); background: rgba(255, 255, 255, .06); }
.feat[aria-current="page"] { color: var(--cv-on-dock); background: var(--cv-dock-raise); box-shadow: inset 3px 0 0 var(--cv-dock-orchid); }
.count {
  position: absolute; top: 4px; right: 8px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
  background: var(--cv-dock-orchid); color: #2A1530; font-size: 11px; font-weight: 750; display: grid; place-items: center;
}
.foot { margin-top: auto; display: grid; justify-items: center; gap: 8px; }
.row { display: none; }
@media (max-width: 720px) {
  .bank { display: none; }
  .row {
    position: sticky; top: 0; z-index: 40; display: flex; align-items: center; gap: 8px; height: 60px; padding: 0 8px 0 10px;
    background: var(--cv-dock); color: var(--cv-on-dock);
  }
  .row .mark { width: 40px; height: 40px; flex: none; }
  .rkeys { list-style: none; margin: 0; padding: 0; display: flex; gap: 6px; overflow-x: auto; flex: 1; scrollbar-width: none; }
  .rkeys :deep(.key) { width: 54px; height: 44px; }
  .menu { position: relative; margin-left: auto; width: 48px; height: 44px; border: 0; border-radius: 10px; background: var(--cv-dock-raise); color: var(--cv-on-dock); display: grid; place-items: center; flex: none; }
  .menu .count { top: -4px; right: -4px; }
}
.drawer { display: grid; gap: 6px; padding-bottom: 12px; }
.wide { width: 100%; grid-auto-flow: column; justify-content: start; gap: 12px; padding: 0 14px; font-size: 15px; min-height: 52px; }
.next.wide { height: 52px; }
.wide .count { position: static; margin-left: auto; }
.acctrow { padding: 10px 14px 0; }
</style>
