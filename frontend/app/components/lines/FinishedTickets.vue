<script setup lang="ts">
// "Finished this morning": rounded tickets with claim number, place, time, name and route tag.
import type { ClaimSummary } from '~/types/api'
import { fmtTime } from '~/utils/format'

defineProps<{ claims: ClaimSummary[] }>()
const placeOf = (c: ClaimSummary) => (c.lossPlace ?? c.regionLabel).split(',').pop()!.trim()
</script>

<template>
  <section class="recent" aria-labelledby="recent-h">
    <h3 id="recent-h">
      Finished this morning <NuxtLink to="/claims">All claims</NuxtLink>
    </h3>
    <div class="tickets">
      <NuxtLink v-for="c in claims" :key="c.id" class="ticket" :to="`/claims/${c.id}`">
        <span class="r1"><span>{{ c.claimNumber }} · {{ placeOf(c) }}</span><time class="num">{{ fmtTime(c.reportedAt) }}</time></span>
        <b>{{ c.holderName }}</b>
        <span class="tags">
          <RouteTag v-if="c.route" :route="c.route.route" :label="c.route.label" />
          <RouteTag v-if="c.siuOpen && c.route?.route !== 'special_investigation'" route="special_investigation" />
        </span>
      </NuxtLink>
    </div>
  </section>
</template>

<style scoped>
.recent { margin: 14px 32px 0; }
h3 { font-family: var(--font-sans); font-size: 14px; font-weight: 750; color: var(--cv-muted); letter-spacing: 0; display: flex; gap: 10px; align-items: baseline; }
h3 a { font-size: 13.5px; }
.tickets { display: flex; gap: 10px; margin-top: 10px; overflow-x: auto; padding: 2px 2px 6px; }
.ticket { flex: 1 0 236px; background: var(--cv-surface); border-radius: 20px; padding: 10px 14px; display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; align-items: center; text-decoration: none; color: inherit; }
.ticket:hover { box-shadow: inset 0 0 0 1.5px var(--cv-orchid-wash); }
.r1 { grid-column: 1 / -1; display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; color: var(--cv-muted); font-weight: 650; }
b { font-size: 14.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tags { display: flex; gap: 4px; }
.tags :deep(.tag) { height: 26px; font-size: 12.5px; }
@media (max-width: 720px) { .recent { margin: 16px 16px 0; } .tickets { flex-direction: column; overflow: visible; } .ticket { flex: none; } }
</style>
