<script setup lang="ts">
// The claim slip under the horizon: each value lands as a pill the moment it's heard (Pluck: a ghost copy flies from
// the words on an arc), updates in place when a later sentence refines it, and the last pill unfurls into the route
// with three reasons (Route).
import type { CallRouteReveal, SlipItem } from '~/utils/landingCall'
import { reasonText } from '~/utils/landingCall'
import { fmtClock } from '~/utils/format'
import { routeStyle, slipIcon } from '~/utils/labels'

const props = defineProps<{ items: SlipItem[], route: CallRouteReveal, showRoute: boolean, animate: boolean, copy: { label: string, empty: string, fromPolicy: string } }>()
const root = ref<HTMLElement | null>(null)
const reduced = useReducedMotionPref()
const lit = ref<string | null>(null)
const style = computed(() => routeStyle(props.route.route))

watch(() => props.items.map(i => i.key).join(','), async (now, before) => {
  const prev = new Set((before ?? '').split(',').filter(Boolean))
  const added = now.split(',').filter(k => k && !prev.has(k))
  if (!props.animate || !added.length) return
  await nextTick()
  for (const k of added) pluck(k)
})

function pluck(key: string) {
  const target = root.value?.querySelector<HTMLElement>(`[data-slip="${key}"]`)
  const src = document.querySelector<HTMLElement>(`.lines .now .span[data-k="${key}"]`) ?? document.querySelector<HTMLElement>(`.lines .span[data-k="${key}"]`)
  if (!target) return
  if (reduced.value || !src || typeof target.animate !== 'function') {
    lit.value = key
    setTimeout(() => { if (lit.value === key) lit.value = null }, 1600)
    return
  }
  const a = src.getBoundingClientRect()
  const b = target.getBoundingClientRect()
  const ghost = document.createElement('span')
  ghost.className = 'heard'
  ghost.textContent = src.textContent
  Object.assign(ghost.style, { position: 'fixed', left: `${a.left}px`, top: `${a.top}px`, zIndex: '50', pointerEvents: 'none', background: 'var(--cv-orchid)', color: 'var(--cv-on-orchid)', boxShadow: 'var(--cv-shadow-lift)', maxWidth: '520px', whiteSpace: 'nowrap', overflow: 'hidden' })
  document.body.appendChild(ghost)
  target.style.opacity = '0'
  const dx = b.left - a.left
  const dy = b.top - a.top
  ghost.animate([
    { transform: 'translate(0,0) scale(1)' },
    { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 60}px) scale(.9)`, offset: 0.5 },
    { transform: `translate(${dx}px, ${dy}px) scale(.8)`, opacity: 0.2 },
  ], { duration: 520, easing: 'cubic-bezier(.2,.8,.2,1)' }).onfinish = () => {
    ghost.remove()
    target.style.opacity = ''
    target.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.06)' }, { transform: 'scale(1)' }], { duration: 220 })
  }
}
</script>

<template>
  <div ref="root" class="slip" role="list" :aria-label="copy.label">
    <span class="label"><CvIcon name="doc" size="s" />{{ copy.label }}</span>
    <span v-if="!items.length" class="empty">{{ copy.empty }}</span>
    <span
      v-for="f in items" :key="f.key" role="listitem" class="heard in" :data-slip="f.key"
      :class="{ hushed: f.hushed, lit: lit === f.key }"
    >
      <span class="ic"><CvIcon :name="f.hushed ? 'card' : slipIcon(f.key)" size="s" /></span>{{ f.label }}
      <span class="at">
        <template v-if="f.fromPolicy">{{ copy.fromPolicy }}</template>
        <template v-else><CvIcon name="play" size="s" class="tri" />{{ fmtClock(f.at) }}</template>
      </span>
    </span>
    <span v-if="showRoute" class="route" role="listitem">
      <span class="tag" :class="style.kind"><CvIcon :name="style.icon" size="s" />{{ route.label }}</span>
      <ol>
        <li v-for="(r, i) in route.reasons" :key="i" :style="{ animationDelay: `${600 + i * 90}ms` }"><b>{{ i + 1 }}</b>{{ reasonText(r) }}</li>
      </ol>
    </span>
  </div>
</template>

<style scoped>
.slip { margin: 14px 40px 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; min-height: 82px; align-content: flex-start; }
.label { font-size: 13px; font-weight: 750; color: var(--cv-muted); margin-right: 6px; display: inline-flex; align-items: center; gap: 6px; }
.heard.in { animation: pop-in 260ms var(--ease-lift) both; }
@keyframes pop-in { from { opacity: 0; transform: scale(.85); } }
.heard .ic { color: var(--cv-orchid-ink); display: inline-flex; }
.heard.lit .ic { color: inherit; }
.at :deep(.tri) { width: 11px; height: 11px; }
.empty { color: var(--cv-faint); font-size: 14px; }
.route { display: inline-flex; align-items: center; gap: 12px; padding: 8px 18px 8px 8px; border-radius: 999px; background: var(--cv-fast-wash); color: var(--cv-ink); animation: route-in var(--m-route) var(--ease-voice) both; }
.route .tag.fast { background: var(--cv-fast); color: var(--cv-on-fast); }
.route .tag.adj { background: var(--cv-adj); color: #fff; }
.route .tag.siu { background: var(--cv-siu); color: #fff; }
.route ol { display: flex; gap: 16px; margin: 0; padding: 0; list-style: none; font-size: 13.5px; font-weight: 550; }
.route li { display: flex; gap: 6px; align-items: center; white-space: nowrap; animation: rise-in 300ms var(--ease-voice) both; }
.route li b { color: var(--cv-fast); font-weight: 800; }
@media (max-width: 720px) {
  .slip { margin: 12px 16px 0; }
  .route { border-radius: 22px; flex-wrap: wrap; padding: 10px 14px; }
  .route ol { flex-direction: column; gap: 4px; }
  .route li { white-space: normal; }
}
</style>
