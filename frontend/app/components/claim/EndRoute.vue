<script setup lang="ts">
// Where it goes, at the end of a call. On a live call that has ended, the routing decision is fetched for its claim
// and shown as the verdict (RouteUnfurl), with a link to the claim file. On the demo line the route arrives with the
// end of the call, so it's passed in directly. Slot `actions` replaces the default link.
import type { EndRoute as EndRouteInfo, RoutingDecision } from '~/types/api'
import { api } from '~/utils/api'
import { routeStyle } from '~/utils/labels'
import { icon } from '~/utils/icons'

const props = withDefaults(defineProps<{
  claimId?: string | null
  route?: EndRouteInfo | null
  nextSteps?: string[]
  title?: string
  reference?: string | null
  nextTitle?: string
  lang?: string
}>(), { claimId: null, route: null, nextSteps: () => [], title: 'Where does it go?', reference: null, nextTitle: 'What happens next', lang: undefined })

const decision = ref<RoutingDecision | null>(null)
const loading = ref(false)
watch(() => props.claimId, async (id) => {
  decision.value = null
  if (!id) return
  loading.value = true
  for (let i = 0; i < 5 && !decision.value; i++) {
    try { decision.value = await api.claims.routing(id) }
    catch { await new Promise(r => setTimeout(r, 800)) }
  }
  loading.value = false
}, { immediate: true })
const slots = useSlots()
const shown = computed(() => !!decision.value || loading.value || !!props.route || props.nextSteps.length > 0 || !!slots.actions)
const simple = computed(() => (props.route ? routeStyle(props.route.route) : null))
</script>

<template>
  <section v-if="shown" class="end" :aria-label="title" :lang="lang">
    <div class="ehead">
      <h3>{{ title }}</h3>
      <span v-if="reference" class="ref num">{{ reference }}</span>
    </div>
    <RouteUnfurl v-if="decision" :decision="decision" compact />
    <div v-else-if="route && simple" class="simple" :class="`k-${simple.kind}`">
      <p class="vword round">
        <span class="vic" aria-hidden="true"><UIcon :name="icon(simple.icon)" /></span>{{ route.label }}
      </p>
      <ol v-if="route.reasons.length" class="why">
        <li v-for="(r, i) in route.reasons" :key="i" :style="{ animationDelay: `${300 + i * 90}ms` }">
          <span class="n num round" aria-hidden="true">{{ i + 1 }}</span>{{ r.text }}
        </li>
      </ol>
    </div>
    <div v-else-if="loading" class="simple" aria-busy="true">
      <USkeleton class="h-12 w-56 rounded-full" /><USkeleton class="h-16 w-full rounded-[22px]" />
    </div>
    <div v-if="nextSteps.length" class="next">
      <span class="label">{{ nextTitle }}</span>
      <ul>
        <li v-for="n in nextSteps" :key="n">
          <UIcon name="i-lucide-check" class="size-4 text-jade-ink" />{{ n }}
        </li>
      </ul>
    </div>
    <div class="acts">
      <slot name="actions">
        <UButton v-if="claimId && decision" :to="`/claims/${claimId}`" color="neutral" trailing-icon="i-lucide-arrow-right">
          Open the claim file
        </UButton>
      </slot>
    </div>
  </section>
</template>

<style scoped>
.end { display: grid; gap: 14px; padding: 22px 24px; border-radius: 28px; background: linear-gradient(180deg, var(--cv-jade-wash), color-mix(in srgb, var(--cv-jade-wash) 30%, var(--cv-bg))); }
.ehead { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.ehead h3 { font-size: 26px; font-weight: 900; }
.ref { color: var(--cv-muted); font-size: 14px; }
.simple { display: grid; gap: 12px; }
.vword { margin: 0; display: flex; align-items: center; gap: 12px; font-size: 36px; font-weight: 900; letter-spacing: -0.02em; line-height: 1.05; }
.vic { width: 48px; height: 48px; border-radius: 50%; display: grid; place-items: center; font-size: 24px; flex: none; background: var(--cv-jade); color: var(--cv-on-jade); animation: pop var(--m-pop) var(--ease-tide) both; }
.k-adj .vic { background: var(--cv-person); color: #fff; }
.k-siu .vic { background: var(--cv-siu); color: #fff; }
.why { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 10px; }
.why li { display: flex; gap: 10px; align-items: flex-start; padding: 12px 14px; border-radius: 20px; background: var(--cv-surface); font-size: 14.5px; line-height: 1.4; animation: rise 300ms var(--ease-tide) both; }
.why .n { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--cv-jade-wash); color: var(--cv-jade-ink); font-weight: 900; font-size: 14px; }
.next { display: grid; gap: 6px; }
.next ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.next li { display: flex; gap: 8px; align-items: center; font-size: 14.5px; }
.acts { display: flex; gap: 8px; flex-wrap: wrap; }
.acts:empty { display: none; }
@media (max-width: 720px) { .end { padding: 18px 16px; } .vword { font-size: 28px; } }
</style>
