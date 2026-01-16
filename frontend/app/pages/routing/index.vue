<script setup lang="ts">
// Routing checks, for compliance (DESIGN.md §3): "Is routing working, and fair?" answered in a sentence, the two
// checks as pebble rows, then the four questions a regulator asks as answer cards (the answer in frequencies with
// its one chart), the "It never" promises, and two sign-offs per version, reviewed in a dialog.
import type { TableColumn } from '@nuxt/ui'
import type { Check, RoutingChecks } from '~/types/api'
import { api } from '~/utils/api'
import { fmtDate } from '~/utils/format'
import { statusStyle } from '~/utils/labels'
import { questionFor } from '~/utils/places'

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
    <PageHead :title="questionFor('routing')" :caption="data?.caption ?? ''">
      <UButton to="/routing/size" color="neutral" variant="soft" icon="i-lucide-file-text" class="hide-phone">
        Fact sheets
      </UButton>
      <UButton :href="api.routing.regulatorPackUrl()" external download color="neutral" icon="i-lucide-download" class="hide-phone">
        Pack for the regulator
      </UButton>
    </PageHead>

    <StateNote v-if="error" kind="error" class="mb-4" title="We couldn't load the routing checks." :body="error" retry @retry="load" />

    <template v-if="data">
      <section class="checks" aria-labelledby="checks-h">
        <h2 id="checks-h" class="pool-h">
          The two checks
        </h2>
        <UTable :data="data.checks" :columns="checkCols" class="tbl" :ui="{ tr: 'cursor-pointer', td: 'align-top whitespace-normal' }" @select="openCheck">
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

      <h2 class="pool-h qh">
        What a regulator asks
      </h2>
      <ol class="qs" aria-label="The four questions">
        <QuestionCard v-for="(q, i) in questions" :key="q.key" :q="q" :n="i + 1" @signoff="signing = candidateCheck" />
      </ol>

      <section class="never" aria-labelledby="never-h">
        <h2 id="never-h">
          It never
        </h2>
        <ul>
          <li v-for="n in data.never" :key="n">
            <span class="x" aria-hidden="true"><UIcon name="i-lucide-x" /></span>{{ n }}
          </li>
        </ul>
      </section>
    </template>

    <div v-else-if="!error" class="loading" aria-busy="true" aria-label="Loading the routing checks">
      <USkeleton class="h-28 w-full rounded-[24px]" />
      <USkeleton v-for="n in 3" :key="n" class="h-56 w-full rounded-[32px]" />
    </div>

    <SignOffSheet :open="!!signing" :check="signing" @close="signing = null" @signed="onSigned" />
  </div>
</template>

<style scoped>
.checks { display: grid; gap: 8px; }
.cname { display: inline-flex; align-items: center; gap: 10px; color: inherit; text-decoration: none; font-family: var(--font-round); font-size: 19px; font-weight: 900; white-space: nowrap; }
.cname:hover { text-decoration: underline; text-decoration-color: var(--cv-seaglass); text-decoration-thickness: 3px; text-underline-offset: 4px; }
.cq { margin: 0; font-size: 15px; font-weight: 500; white-space: normal; }
.cd { margin: 2px 0 0; font-size: 13px; color: var(--cv-muted); white-space: normal; }
.qh { margin-top: 40px; }
.qs { margin: 14px 0 0; padding: 0; list-style: none; display: grid; gap: 16px; }
.never { margin-top: 40px; display: grid; gap: 12px; }
.never h2 { font-size: 26px; font-weight: 900; }
.never ul { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px; }
.never li { display: inline-flex; align-items: center; gap: 10px; padding: 8px 16px 8px 8px; border-radius: 999px; background: var(--cv-surface); font-size: 14.5px; }
.x { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-urgent-wash); color: var(--cv-urgent); flex: none; }
.loading { display: grid; gap: 16px; }
</style>
