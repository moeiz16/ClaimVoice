<script setup lang="ts">
// "Waiting for a person": urgent safety first (red ring, wait counting up in red), then people who asked. Each item
// carries a two-line summary so nobody asks the caller twice. At the foot, who is free.
import { motion } from 'motion-v'
import type { HandoffInfo, PersonRef } from '~/types/api'
import { firstName, initials, joinWords } from '~/utils/format'

defineProps<{ items: HandoffInfo[], free: PersonRef[] }>()
const { can } = useSession()
const listening = useListening()
const clock = useDemoClock()
const reduced = useReducedMotionPref()
const open = ref<string | null>(null)

function asLine(h: HandoffInfo) {
  return { callId: h.callId, lineLabel: h.lineLabel, callerLabel: h.callerLabel, place: h.place, language: h.language, answeredAt: h.requestedAt }
}
async function take(h: HandoffInfo) {
  if (await listening.acceptHandoff(listening.fromLine(asLine(h)))) await navigateTo(`/lines/${h.callId}`)
}
</script>

<template>
  <aside class="tray" aria-labelledby="tray-h">
    <h2 id="tray-h">
      Waiting for a person <span class="n num">{{ items.length }}</span>
    </h2>
    <motion.div
      v-for="h in items" :key="h.id" :layout-id="`call-${h.callId}`" class="wait" :class="{ urgent: h.priority === 'urgent' }"
      :initial="reduced ? { opacity: 0 } : { opacity: 0, x: h.priority === 'urgent' ? -40 : 0 }" :animate="{ opacity: 1, x: 0 }"
      :transition="reduced ? { duration: 0.15 } : { type: 'spring', stiffness: 260, damping: 26 }"
    >
      <div class="row">
        <span v-if="h.priority === 'urgent'" class="tag urgent"><CvIcon name="urgent" size="s" />{{ h.reasonLabel }}</span>
        <span v-else class="tag adj"><CvIcon name="person" size="s" />{{ h.reasonLabel }}</span>
        <time class="t num" :class="{ calm: h.priority !== 'urgent' }" :aria-label="`Waiting ${clock.elapsed(h.requestedAt)}`"><CvIcon v-if="h.priority === 'urgent'" name="clock" size="s" />{{ clock.elapsed(h.requestedAt) }}</time>
      </div>
      <b class="name">{{ h.callerLabel }} · {{ h.lineLabel }}</b>
      <p>{{ h.detail }}<template v-if="h.place && !h.detail.includes(h.place)">{{ ' ' }}{{ h.place }}.</template></p>
      <p v-if="h.actionsTaken.length" class="note">
        ClaimVoice {{ h.actionsTaken.map(a => a.charAt(0).toLowerCase() + a.slice(1)).join('; ') }}.
      </p>
      <p v-if="open === h.id" class="summary">
        {{ h.summary }}
      </p>
      <div class="acts">
        <button v-if="can('calls:handoff')" class="btn sm" :class="h.priority === 'urgent' ? 'primary' : 'ink'" type="button" @click="take(h)">
          <CvIcon v-if="h.priority === 'urgent'" name="phone" size="s" />Take the call
        </button>
        <button v-if="h.priority === 'urgent' && can('calls:listen')" class="btn soft sm" type="button" @click="listening.listen(asLine(h))">
          Listen first
        </button>
        <button v-else class="btn soft sm" type="button" :aria-expanded="open === h.id" @click="open = open === h.id ? null : h.id">
          {{ open === h.id ? 'Hide the summary' : 'Read the summary' }}
        </button>
      </div>
    </motion.div>
    <p v-if="!items.length" class="none">
      <CvIcon name="check" size="s" />Nobody is waiting. ClaimVoice has every line.
    </p>
    <div v-if="free.length" class="free">
      <span class="faces"><span v-for="p in free.slice(0, 4)" :key="p.id">{{ initials(p.name) }}</span></span>{{ joinWords(free.map(p => firstName(p.name))) }} {{ free.length === 1 ? 'is' : 'are' }} free to take calls
    </div>
  </aside>
</template>

<style scoped>
.tray { background: var(--cv-sunk); border-radius: 28px; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
h2 { font-size: 21px; font-weight: 700; letter-spacing: -0.02em; display: flex; align-items: center; gap: 8px; }
.n { font-family: var(--font-sans); font-size: 13px; background: var(--cv-surface); border-radius: 999px; padding: 2px 10px; }
.wait { background: var(--cv-surface); border-radius: 20px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }
.wait.urgent { box-shadow: inset 0 0 0 2px var(--cv-urgent); }
.row { display: flex; align-items: center; gap: 8px; }
.t { margin-left: auto; font-weight: 750; font-size: 13.5px; color: var(--cv-urgent); display: inline-flex; gap: 4px; align-items: center; }
.t.calm { color: var(--cv-muted); }
.name { font-family: var(--font-display); font-size: 19px; font-weight: 700; letter-spacing: -0.02em; }
p { margin: 0; font-size: 14px; }
.note, .summary { color: var(--cv-muted); font-size: 13.5px; }
.summary { background: var(--cv-sunk); border-radius: 14px; padding: 8px 10px; color: var(--cv-ink); }
.acts { display: flex; gap: 8px; flex-wrap: wrap; }
.none { color: var(--cv-muted); display: flex; gap: 6px; align-items: center; font-size: 14px; }
.free { margin-top: auto; font-size: 13px; color: var(--cv-muted); display: flex; gap: 8px; align-items: center; }
.faces { display: flex; padding-left: 6px; flex: none; }
.faces span { width: 30px; height: 30px; border-radius: 50%; background: var(--cv-person-wash); color: var(--cv-person); font-size: 10.5px; font-weight: 800; display: grid; place-items: center; box-shadow: 0 0 0 2px var(--cv-sunk); margin-left: -6px; }
</style>
