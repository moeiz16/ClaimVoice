<script setup lang="ts">
// Routing checks, for compliance (DESIGN.md §5.6). The slate, the two checks as one register, then the four
// questions a regulator asks as numbered sections (the answer in frequencies on the left, its one chart on the
// right), the "It never" list, and two sign-offs per version, reviewed in a dialog.
import type { TableColumn } from '@nuxt/ui'
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
async function onSigned() { await load() }

const checkCols: TableColumn<Check>[] = [
  { accessorKey: 'name', header: 'Check' },
  { accessorKey: 'question', header: 'The question it answers' },
  { id: 'version', header: 'Version' },
  { id: 'since', header: 'In use since', cell: ({ row }) => (row.original.inUse.inUseSince ? fmtDate(row.original.inUse.inUseSince) : '—') },
  { id: 'signed', header: 'Signed off by', cell: ({ row }) => row.original.signedBy?.name ?? '—' },
  { id: 'status', header: 'How it is doing' },
]
function openCheck(row: { original: Check }) { void navigateTo(`/routing/${row.original.key}`) }
</script>

<template>
  <div>
    <Slate title="Routing checks" :caption="data?.caption ?? ''">
      <UButton to="/routing/size" color="neutral" variant="soft" icon="i-lucide-file-text" class="hide-phone">
        Fact sheets
      </UButton>
      <UButton :href="api.routing.regulatorPackUrl()" external download color="neutral" icon="i-lucide-download" class="hide-phone">
        Pack for the regulator
      </UButton>
    </Slate>

    <StateNote v-if="error" kind="error" class="m-4 sm:mx-8" title="We couldn't load the routing checks." :body="error" retry @retry="load" />

    <template v-if="data">
      <section class="checks" aria-labelledby="checks-h">
        <h2 id="checks-h" class="sr-only-cv">
          The two checks
        </h2>
        <UTable :data="data.checks" :columns="checkCols" class="tbl" :ui="{ tr: 'cursor-pointer hover:bg-sunk', td: 'align-top whitespace-normal' }" @select="openCheck">
          <template #name-cell="{ row }">
            <NuxtLink :to="`/routing/${row.original.key}`" class="cname">
              <UIcon :name="row.original.key === 'size' ? 'i-lucide-user-round' : 'i-lucide-search'" class="size-5 shrink-0" />{{ row.original.name }}
            </NuxtLink>
          </template>
          <template #question-cell="{ row }">
            <p class="cq">
              {{ row.original.question }}
            </p>
            <p class="cd">
              {{ row.original.decides }}
            </p>
          </template>
          <template #version-cell="{ row }">
            <span class="num font-semibold">Version {{ row.original.inUse.version }}</span>
            <span v-if="row.original.candidate" class="cd block">Version {{ row.original.candidate.version }} is on trial</span>
          </template>
          <template #status-cell="{ row }">
            <CvTag :kind="statusStyle(row.original.status).kind" :icon="statusStyle(row.original.status).icon" class="whitespace-nowrap">
              {{ row.original.statusLabel }}
            </CvTag>
          </template>
        </UTable>
      </section>

      <ol class="qs" aria-label="The four questions">
        <QuestionCard v-for="(q, i) in questions" :key="q.key" :q="q" :n="i + 1" @signoff="signing = candidateCheck" />
      </ol>

      <section class="never" aria-labelledby="never-h">
        <h2 id="never-h">
          It never
        </h2>
        <ul>
          <li v-for="n in data.never" :key="n">
            <CvTag kind="plain" icon="x">
              {{ n }}
            </CvTag>
          </li>
        </ul>
      </section>
    </template>

    <div v-else-if="!error" class="loading" aria-busy="true" aria-label="Loading the routing checks">
      <USkeleton class="h-28 w-full" />
      <div v-for="n in 4" :key="n" class="skel">
        <USkeleton class="h-8 w-2/5" /><USkeleton class="h-40 w-full" />
      </div>
    </div>

    <SignOffSheet :open="!!signing" :check="signing" @close="signing = null" @signed="onSigned" />
  </div>
</template>

<style scoped>
.checks { padding: 0 32px; border-bottom: 1px solid var(--cv-rule); }
.cname { display: inline-flex; align-items: center; gap: 8px; color: inherit; text-decoration: none; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 18px; font-weight: 680; white-space: nowrap; }
.cname:hover { text-decoration: underline; text-underline-offset: 4px; }
.cq { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 16px; font-weight: 560; color: var(--cv-caller); white-space: normal; }
.cd { margin: 2px 0 0; font-size: 13px; color: var(--cv-muted); white-space: normal; }
.qs { margin: 0; padding: 0; list-style: none; }
.never { padding: 22px 32px 32px; display: grid; grid-template-columns: 200px 1fr; gap: 12px 24px; align-items: start; }
.never h2 { font-size: 22px; font-weight: 700; }
.never ul { margin: 0; padding: 0; list-style: none; }
.never li { padding: 8px 0; border-bottom: 1px solid var(--cv-rule); }
.never li:first-child { border-top: 1px solid var(--cv-rule); }
.loading { display: grid; gap: 0; }
.loading > :first-child { margin: 16px 32px; width: auto; }
.skel { display: grid; gap: 14px; padding: 24px 32px; border-top: 1px solid var(--cv-rule); }
@media (max-width: 720px) {
  .checks { padding: 0 16px; overflow-x: auto; }
  .never { padding: 18px 16px 24px; grid-template-columns: 1fr; }
  .skel { padding: 18px 16px; }
  .loading > :first-child { margin: 12px 16px; }
}
</style>
