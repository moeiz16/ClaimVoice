<script setup lang="ts">
// When a live call ends, the route unfurls at the top of its claim file.
import type { RoutingDecision } from '~/types/api'
import { api } from '~/utils/api'

const props = defineProps<{ claimId: string }>()
const decision = ref<RoutingDecision | null>(null)
watch(() => props.claimId, async (id) => {
  decision.value = null
  for (let i = 0; i < 5 && !decision.value; i++) {
    try { decision.value = await api.claims.routing(id) }
    catch { await new Promise(r => setTimeout(r, 800)) }
  }
}, { immediate: true })
</script>

<template>
  <div v-if="decision" class="end sect-like">
    <RouteUnfurl :decision="decision" compact />
    <NuxtLink class="btn sm soft" :to="`/claims/${claimId}`">
      Open the claim file<CvIcon name="right" size="s" />
    </NuxtLink>
  </div>
</template>

<style scoped>
.end { background: var(--cv-surface); border-radius: 20px; padding: 4px 14px 14px; display: grid; gap: 10px; }
.end :deep(.why li) { background: var(--cv-sunk); }
.end .btn { justify-self: start; }
</style>
