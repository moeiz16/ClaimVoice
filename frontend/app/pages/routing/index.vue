<script setup lang="ts">
// Routing checks, for compliance (DESIGN.md §5.6): the two checks as wide cards, the four questions a regulator
// asks (answered in frequencies, one chart each), the "It never" pills, and two sign-offs per version.
import type { Check, RoutingChecks } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDate } from '~/utils/format'
import { statusStyle } from '~/utils/labels'

useHead({ title: 'Routing checks · ClaimVoice' })
const data = ref<RoutingChecks | null>(null)
const error = ref<string | null>(null)
const signing = ref<Check | null>(null)

async function load() {
  error.value = null
  try { data.value = await api.routing.checks() }
  catch (e) { error.value = (e as Error).message }
}
onMounted(load)

const order = ['right', 'fair', 'like_learned', 'replace']
const questions = computed(() => [...(data.value?.questions ?? [])].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key)))
const candidateCheck = computed(() => data.value?.checks.find(c => c.candidate) ?? null)
function versionLine(c: Check) {
  const since = c.inUse.inUseSince ? `, in use since ${fmtDate(c.inUse.inUseSince)}` : ''
  const by = c.signedBy ? `, signed off by ${c.signedBy.name}` : ''
  return `Version ${c.inUse.version}${since}${by}.`
}
async function onSigned() { await load() }
</script>

<template>
  <div>
    <PageHeader title="Routing checks" :caption="data?.caption ?? ''">
      <NuxtLink class="btn soft sm hide-phone" to="/routing/size">
        <CvIcon name="doc" size="s" />Fact sheets
      </NuxtLink>
      <a class="btn ink sm hide-phone" :href="api.routing.regulatorPackUrl()" download>Pack for the regulator</a>
    </PageHeader>
    <StateNote v-if="error" kind="error" title="We couldn't load the routing checks." :body="error" retry class="wrap" @retry="load" />
    <template v-if="data">
      <section class="checks wrap" aria-label="The two checks">
        <NuxtLink v-for="c in data.checks" :key="c.key" class="check" :to="`/routing/${c.key}`">
          <span class="ic"><CvIcon :name="c.key === 'size' ? 'person' : 'look'" size="l" /></span>
          <h2>{{ c.name }}</h2>
          <CvTag :kind="statusStyle(c.status).kind" :icon="statusStyle(c.status).icon" class="st">{{ c.statusLabel }}</CvTag>
          <p class="qline">{{ c.question }}</p>
          <p>{{ c.decides }} {{ versionLine(c) }}<template v-if="c.candidate"> Version {{ c.candidate.version }} is on trial.</template></p>
        </NuxtLink>
      </section>
      <main class="qa wrap">
        <QuestionCard v-for="q in questions" :key="q.key" :q="q" :tint="q.key === 'like_learned' || q.key === 'replace'" @signoff="signing = candidateCheck" />
      </main>
      <div class="never wrap">
        <span>It never</span>
        <CvTag v-for="n in data.never" :key="n" kind="plain" icon="x">{{ n }}</CvTag>
      </div>
    </template>
    <div v-else-if="!error" class="qa wrap" aria-busy="true">
      <span v-for="n in 4" :key="n" class="skeleton" style="height: 320px; border-radius: 28px" />
    </div>
    <SignOffSheet :open="!!signing" :check="signing" @close="signing = null" @signed="onSigned" />
  </div>
</template>

<style scoped>
.wrap { margin-left: 32px; margin-right: 32px; }
.checks { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.check { background: var(--cv-surface); border-radius: 28px; padding: 18px 22px; display: grid; grid-template-columns: 52px 1fr auto; grid-template-areas: "ic h st" "ic q q" "ic p p"; gap: 4px 16px; align-items: center; text-decoration: none; color: inherit; }
.check h2 { grid-area: h; } .check .qline { grid-area: q; } .check p:not(.qline) { grid-area: p; }
.check:hover { box-shadow: inset 0 0 0 1.5px var(--cv-orchid-wash); }
.ic { grid-area: ic; align-self: start; width: 52px; height: 52px; border-radius: 50%; background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); display: grid; place-items: center; }
.check h2 { font-size: 23px; font-weight: 700; letter-spacing: -0.025em; }
.check :deep(.st) { grid-area: st; justify-self: end; }
.check p { margin: 0; color: var(--cv-muted); font-size: 14px; }
.check p.qline { font-family: var(--font-display); font-size: 19px; font-weight: 600; color: var(--cv-caller); letter-spacing: -0.015em; }
.qa { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
.never { margin-top: 14px; display: flex; gap: 10px 12px; flex-wrap: wrap; align-items: center; font-size: 14px; font-weight: 600; }
.never > span:first-child { font-family: var(--font-display); font-size: 18px; font-weight: 700; margin-right: 6px; }
@media (max-width: 1100px) { .checks, .qa { grid-template-columns: 1fr; } }
@media (max-width: 720px) {
  .wrap { margin-left: 16px; margin-right: 16px; }
  .check { grid-template-columns: 44px 1fr; grid-template-areas: "ic h" "ic st" "q q" "p p"; }
  .check :deep(.st) { justify-self: start; }
  .ic { width: 44px; height: 44px; }
}
</style>
