<script setup lang="ts">
// Change route: the three routes as large radio pills, a required reason (free text or a common reason), and who is
// told. The change is written to the activity log.
import type { Route, RoutingDecision } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'
import { routeStyle } from '~/utils/labels'

const props = defineProps<{ open: boolean, claimId: string, current: Route, claimNumber: string }>()
const emit = defineEmits<{ close: [], changed: [d: RoutingDecision] }>()
const route = ref<Route>(props.current)
const reason = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
watch(() => props.open, (o) => { if (o) { route.value = props.current; reason.value = ''; error.value = null } })
const options: { route: Route, sub: string }[] = [
  { route: 'fast_track', sub: 'Paid quickly from the photos; no visit' },
  { route: 'adjuster', sub: 'An adjuster calls and works the claim' },
  { route: 'special_investigation', sub: 'Special investigations looks first. Never a denial.' },
]
const common = ['Police report confirms the details', 'Damage is larger than it sounded', 'Caller needs a person', 'Photos show minor damage only']
const notify = computed(() => (route.value === 'special_investigation' ? 'Dev Malhotra in special investigations and the assigned adjuster are told.' : route.value === 'adjuster' ? 'The adjusters\' queue and the caller\'s next-steps text are updated.' : 'The caller gets a fast-track text with the photo link.'))

async function save() {
  if (!reason.value.trim()) { error.value = 'Give a reason for the change.'; return }
  busy.value = true
  error.value = null
  try {
    emit('changed', await api.claims.overrideRoute(props.claimId, route.value, reason.value.trim()))
    emit('close')
  }
  catch (e) { error.value = e instanceof ApiError ? (e.fieldError('reason') ?? e.message) : 'That didn\'t save. Try again.' }
  busy.value = false
}
</script>

<template>
  <CvSheet :open="open" :title="`Change the route of ${claimNumber}`" @close="emit('close')">
    <form @submit.prevent="save">
      <fieldset>
        <legend class="sr-only-cv">
          Route
        </legend>
        <label v-for="o in options" :key="o.route" class="opt" :class="[routeStyle(o.route).kind, { on: route === o.route }]">
          <input v-model="route" type="radio" name="route" :value="o.route">
          <CvIcon :name="routeStyle(o.route).icon" />
          <span><b>{{ routeStyle(o.route).label }}</b><small>{{ o.sub }}</small></span>
        </label>
      </fieldset>
      <label class="lab" for="route-reason">Reason (required)</label>
      <textarea id="route-reason" v-model="reason" class="field-input" maxlength="280" :aria-invalid="!!error" placeholder="Police report confirms the SUV." />
      <div class="quick">
        <button v-for="q in common" :key="q" class="tag plain" type="button" @click="reason = q">
          {{ q }}
        </button>
      </div>
      <p class="notify">
        <CvIcon name="person" size="s" />{{ notify }} The change is logged with your name.
      </p>
      <p v-if="error" class="err" role="alert">
        <CvIcon name="urgent" size="s" />{{ error }}
      </p>
      <div class="acts">
        <button class="btn primary" type="submit" :disabled="busy || route === current && !reason.trim()">
          Change the route
        </button>
        <button class="btn soft" type="button" @click="emit('close')">
          Keep it
        </button>
      </div>
    </form>
  </CvSheet>
</template>

<style scoped>
fieldset { border: 0; padding: 0; margin: 0 0 14px; display: grid; gap: 8px; }
.opt { display: flex; align-items: center; gap: 12px; padding: 12px 18px; border-radius: 999px; background: var(--cv-sunk); cursor: pointer; }
.opt input { accent-color: var(--cv-orchid); width: 18px; height: 18px; }
.opt b { display: block; font-size: 16px; }
.opt small { color: var(--cv-muted); font-size: 13px; }
.opt.fast :deep(svg) { color: var(--cv-fast); } .opt.adj :deep(svg) { color: var(--cv-adj); } .opt.siu :deep(svg) { color: var(--cv-siu); }
.opt.on.fast { background: var(--cv-fast-wash); box-shadow: inset 0 0 0 2px var(--cv-fast); }
.opt.on.adj { background: var(--cv-adj-wash); box-shadow: inset 0 0 0 2px var(--cv-adj); }
.opt.on.siu { background: var(--cv-siu-wash); box-shadow: inset 0 0 0 2px var(--cv-siu); }
.lab { display: block; font-size: 13px; font-weight: 700; color: var(--cv-muted); margin: 6px 0; }
.quick { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.quick .tag { border: 0; padding: 0 12px; }
.notify { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-size: 13.5px; margin: 14px 0 0; }
.err { display: flex; gap: 6px; align-items: center; color: var(--cv-urgent); font-weight: 600; font-size: 14px; margin: 10px 0 0; }
.acts { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
</style>
