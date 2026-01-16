<script setup lang="ts">
// The Bell (DESIGN.md §3): top right of every page for people who watch the lines. A round button with the number of
// callers waiting for a person inside a ring; it nudges once when someone new starts waiting. Its popover lists who
// is waiting (urgent first, with Take the call) and, when you're listening, the line you're on: a live level,
// Whisper, Take over or Hand back, Hand off, Stop listening. Its name says all of it in words.
import { boardRows } from '~/utils/board'
import { firstName, initials } from '~/utils/format'

const { can } = useSession()
const { snapshot } = useSwitchboard(can('lines:read'))
const listening = useListening()
const clock = useDemoClock()
const reduced = useReducedMotionPref()
const route = useRoute()
const open = ref(false)
const text = ref('')

const rows = computed(() => (snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []))
const waiting = computed(() => rows.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting'))
const urgent = computed(() => waiting.value.some(r => r.lamp === 'urgent'))
const onLine = computed(() => listening.onLine.value)
const tookOver = computed(() => onLine.value?.mode === 'took_over')

// Nudge when the number waiting goes up.
const nudge = ref(false)
let nudgeTimer: ReturnType<typeof setTimeout> | null = null
watch(() => waiting.value.length, (n, o) => {
  if (o === undefined || n <= o || reduced.value) return
  nudge.value = false
  if (nudgeTimer) clearTimeout(nudgeTimer)
  requestAnimationFrame(() => { nudge.value = true; nudgeTimer = setTimeout(() => { nudge.value = false }, 1000) })
})
onBeforeUnmount(() => { if (nudgeTimer) clearTimeout(nudgeTimer) })
watch(() => route.fullPath, () => { open.value = false })

const name = computed(() => {
  const n = waiting.value.length
  const bits = [n ? `${n} caller${n > 1 ? 's' : ''} waiting for a person${urgent.value ? ', one urgent' : ''}` : 'Nobody is waiting for a person']
  if (onLine.value) bits.push(tookOver.value ? `you're on ${onLine.value.callerLabel}'s call` : `you're listening to ${onLine.value.callerLabel}`)
  return bits.join('; ')
})

async function take(r: (typeof waiting.value)[number]) {
  const l = listening.fromLine({ callId: r.callId, lineLabel: r.lineLabel, callerLabel: r.callerLabel, place: r.place, language: r.language, answeredAt: r.since })
  if (await listening.acceptHandoff(l)) await navigateTo(`/lines/${r.callId}`)
}
async function send() {
  if (!onLine.value || !text.value.trim()) return
  if (await listening.whisper(onLine.value.callId, text.value.trim())) text.value = ''
}
</script>

<template>
  <UPopover v-if="can('lines:read')" v-model:open="open" :content="{ side: 'bottom', align: 'end', sideOffset: 10 }">
    <button
      type="button" class="bell" :class="{ has: waiting.length, urgent, on: !!onLine, nudge }"
      :aria-label="name" data-shell
    >
      <span class="ring" aria-hidden="true" />
      <span v-if="waiting.length" class="n num" aria-hidden="true">{{ waiting.length }}</span>
      <UIcon v-else name="i-lucide-bell" class="size-6" />
      <span v-if="onLine" class="ear" aria-hidden="true"><UIcon :name="tookOver ? 'i-lucide-phone' : 'i-lucide-headphones'" class="size-3.5" /></span>
      <span class="word" aria-hidden="true">{{ waiting.length ? 'waiting' : 'all fine' }}</span>
    </button>

    <template #content>
      <div class="pop">
        <section v-if="onLine" class="online" aria-label="The line you're on">
          <div class="olhead">
            <span class="live-dot" aria-hidden="true" />
            <div>
              <b class="round">{{ onLine.callerLabel }}</b>
              <small v-if="tookOver">You're on the call · ClaimVoice is taking notes</small>
              <small v-else>{{ onLine.lineLabel }}{{ onLine.place ? ` · ${onLine.place}` : '' }} · <time class="num">{{ clock.elapsed(onLine.answeredAt) }}</time></small>
            </div>
          </div>
          <div class="lvl">
            <LiveWave :seed-key="onLine.callId" :label="`${onLine.callerLabel}'s call, live`" />
          </div>
          <form v-if="!tookOver && can('calls:whisper')" class="say" @submit.prevent="send">
            <UInput v-model="text" maxlength="280" size="md" class="flex-1" :placeholder="`Whisper to ClaimVoice. ${firstName(onLine.callerLabel)} won't hear it.`" aria-label="Whisper to ClaimVoice" />
            <UButton type="submit" size="md" color="neutral" variant="soft" icon="i-lucide-send" :disabled="!text.trim()" aria-label="Send the whisper" />
          </form>
          <div class="acts">
            <UButton size="md" icon="i-lucide-headphone-off" color="neutral" variant="soft" @click="listening.stop()">
              {{ tookOver ? 'Leave the call' : 'Stop listening' }}
            </UButton>
            <UButton v-if="!tookOver && can('calls:takeover')" size="md" icon="i-lucide-phone" color="neutral" @click="listening.takeoverFor.value = onLine">
              Take over
            </UButton>
            <UButton v-else-if="tookOver" size="md" icon="i-lucide-arrow-left-right" color="info" @click="listening.giveBack(onLine.callId)">
              Hand back
            </UButton>
            <UButton v-if="can('calls:handoff')" size="md" icon="i-lucide-user-round-plus" color="neutral" variant="soft" @click="listening.handoffFor.value = onLine">
              Hand off
            </UButton>
            <UButton :to="`/lines/${onLine.callId}`" size="md" color="primary" variant="link" trailing-icon="i-lucide-arrow-right">
              Open the call
            </UButton>
          </div>
        </section>

        <section aria-label="Waiting for a person">
          <h2 class="ph2">
            {{ waiting.length ? 'Waiting for a person' : 'Nobody is waiting' }}
          </h2>
          <ul v-if="waiting.length" class="wl">
            <li v-for="r in waiting" :key="r.callId" :class="{ urgent: r.lamp === 'urgent' }">
              <span class="av" aria-hidden="true">{{ initials(r.callerLabel) }}</span>
              <span class="wt">
                <NuxtLink :to="`/lines/${r.callId}`"><b>{{ r.callerLabel }}</b></NuxtLink>
                <small><UIcon :name="r.lamp === 'urgent' ? 'i-lucide-triangle-alert' : 'i-lucide-hand'" class="size-3.5" />{{ r.stateWord }} · <time class="num">{{ clock.elapsed(r.since) }}</time></small>
              </span>
              <UButton v-if="can('calls:handoff')" size="sm" :color="r.lamp === 'urgent' ? 'error' : 'primary'" icon="i-lucide-phone" @click="take(r)">
                Take
              </UButton>
            </li>
          </ul>
          <p v-else class="calm">
            ClaimVoice has every line. You'll see a number here the moment a caller asks for a person.
          </p>
          <UButton to="/lines" color="primary" variant="link" trailing-icon="i-lucide-arrow-right" size="md">
            Who's on the line?
          </UButton>
        </section>
      </div>
    </template>
  </UPopover>
</template>

<style scoped>
.bell {
  position: relative; width: 72px; height: 72px; border: 0; border-radius: 50%; display: grid; place-items: center;
  background: var(--cv-surface); color: var(--cv-muted); box-shadow: var(--cv-shadow-soft), inset 0 -3px 0 var(--cv-lip);
  transition: transform 160ms var(--ease-spring);
}
.bell:active { transform: translateY(2px); }
.ring { position: absolute; inset: 5px; border-radius: 50%; border: 3px solid var(--cv-sunk-2); }
.has .ring { border-color: var(--cv-siu); border-style: solid; }
.urgent .ring { border-color: var(--cv-urgent); }
.n { font-family: var(--font-round); font-weight: 900; font-size: 28px; line-height: 1; color: var(--cv-ink); margin-top: -8px; }
.word { position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; font-size: 10.5px; font-weight: 500; color: var(--cv-muted); }
.has .word { color: var(--cv-siu); }
.urgent .word { color: var(--cv-urgent); }
.bell:not(.has) .size-6 { margin-top: -10px; }
.ear { position: absolute; top: -2px; right: -2px; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-jade); color: var(--cv-on-jade); box-shadow: 0 0 0 3px var(--cv-bg); }
.nudge { animation: nudge 900ms var(--ease-tide) 1; transform-origin: 50% 10%; }

.pop { width: min(420px, calc(100vw - 24px)); padding: 16px; display: grid; gap: 16px; }
.online { display: grid; gap: 10px; padding: 14px; border-radius: 20px; background: var(--cv-jade-wash); }
.olhead { display: flex; gap: 10px; align-items: center; }
.olhead b { display: block; font-size: 19px; font-weight: 900; }
.olhead small { color: var(--cv-muted); font-size: 13px; }
.lvl { height: 34px; }
.say { display: flex; gap: 6px; }
.acts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.ph2 { font-size: 20px; font-weight: 900; margin-bottom: 8px; }
.wl { list-style: none; margin: 0 0 6px; padding: 0; display: grid; gap: 6px; }
.wl li { display: flex; align-items: center; gap: 10px; padding: 8px 8px 8px 8px; border-radius: 18px; background: var(--cv-siu-wash); }
.wl li.urgent { background: var(--cv-urgent-wash); }
.av { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-surface); font-family: var(--font-round); font-weight: 900; font-size: 14px; flex: none; }
.wt { flex: 1; min-width: 0; display: grid; }
.wt a { color: inherit; text-decoration: none; }
.wt b { font-weight: 600; }
.wt small { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--cv-siu); font-weight: 500; }
.urgent .wt small { color: var(--cv-urgent); }
.calm { margin: 0 0 6px; color: var(--cv-muted); font-size: 14px; }
@media (max-width: 720px) {
  .bell { width: 56px; height: 56px; }
  .n { font-size: 24px; margin-top: 0; }
  .word { display: none; }
  .bell:not(.has) .size-6 { margin-top: 0; }
}
</style>
