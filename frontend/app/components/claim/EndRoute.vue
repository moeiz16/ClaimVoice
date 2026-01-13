<script setup lang="ts">
// Section 8 of the loss notice: where the claim goes. On a live call that has ended, the routing decision is fetched
// for its claim and unfurls (RouteUnfurl), with a link to the claim file. On the demo line the route arrives with the
// end of the call, so it's passed in directly: the route tag unfurls and its reasons stagger in, then what happens
// next. Slot `actions` replaces the default link.
import type { EndRoute as EndRouteInfo, RoutingDecision } from '~/types/api'
import { api } from '~/utils/api'

const props = withDefaults(defineProps<{
  claimId?: string | null
  route?: EndRouteInfo | null
  nextSteps?: string[]
  title?: string
  reference?: string | null
  nextTitle?: string
  lang?: string
}>(), { claimId: null, route: null, nextSteps: () => [], title: 'Where it goes', reference: null, nextTitle: 'What happens next', lang: undefined })

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
</script>

<template>
  <section v-if="shown" class="sec8" :aria-label="`8. ${title}`" :lang="lang">
    <div class="shead">
      <span class="no num" aria-hidden="true">8</span>
      <h3>{{ title }}</h3>
      <span v-if="reference" class="ref num">{{ reference }}</span>
    </div>
    <div class="body">
      <RouteUnfurl v-if="decision" :decision="decision" compact />
      <div v-else-if="route" class="simple">
        <RouteTag :route="route.route" :label="route.label" lg class="unfurl" />
        <ol v-if="route.reasons.length" class="why">
          <li v-for="(r, i) in route.reasons" :key="i" :style="{ animationDelay: `${600 + i * 90}ms` }">
            <span class="n num" aria-hidden="true">{{ i + 1 }}</span>{{ r.text }}
          </li>
        </ol>
      </div>
      <div v-else-if="loading" class="simple" aria-busy="true">
        <USkeleton class="h-8 w-40" /><USkeleton class="h-5 w-3/4" />
      </div>
      <div v-if="nextSteps.length" class="next">
        <span class="label">{{ nextTitle }}</span>
        <ul>
          <li v-for="n in nextSteps" :key="n">
            <UIcon name="i-lucide-check" class="size-4 text-fast" />{{ n }}
          </li>
        </ul>
      </div>
    </div>
    <div class="acts">
      <slot name="actions">
        <UButton v-if="claimId && decision" :to="`/claims/${claimId}`" color="neutral" variant="soft" trailing-icon="i-lucide-arrow-right">
          Open the claim file
        </UButton>
      </slot>
    </div>
  </section>
</template>

<style scoped>
.sec8 { display: grid; gap: 0; }
.shead { display: flex; align-items: center; gap: 10px; padding: 0 0 8px; }
.no {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 15px;
  background: var(--cv-orchid); color: var(--cv-on-orchid);
}
.shead h3 { font-size: 17px; font-weight: 650; }
.ref { margin-left: auto; color: var(--cv-muted); font-size: 13.5px; font-weight: 600; }
.body {
  display: grid; gap: 14px; padding: 14px 16px 16px; background: var(--cv-surface);
  border: 1px solid var(--cv-rule); border-radius: 6px;
}
.simple { display: grid; gap: 12px; justify-items: start; }
.unfurl { animation: route-in var(--m-route) var(--ease-voice) both; }
.why { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; border-top: 1px solid var(--cv-rule); }
.why li {
  display: flex; gap: 10px; align-items: baseline; padding: 10px 12px 4px 0; font-size: 14.5px; font-weight: 550;
  animation: rise-in 300ms var(--ease-voice) both;
}
.why .n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; color: var(--cv-orchid-ink); font-size: 16px; }
.next { display: grid; gap: 6px; border-top: 1px solid var(--cv-rule); padding-top: 12px; }
.next ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.next li { display: flex; gap: 6px; align-items: center; font-size: 14.5px; }
.acts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.acts:empty { display: none; }
@media (max-width: 720px) {
  .why { grid-template-columns: minmax(0, 1fr); }
}
</style>
