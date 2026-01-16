<script setup lang="ts">
// The Questions sheet (DESIGN.md §3): ClaimVoice's navigation. It drops from the page's question and lists every
// place the person can open as the question it answers, with its short name and a count; Find sits above them
// (lines on the board, this morning's claims, a claim search) and the person's own settings sit below (Night line,
// caption size, Reduce motion, Sign out). Arrow keys move between options; Enter opens one.
import { api } from '~/utils/api'
import { boardRows } from '~/utils/board'
import { initials } from '~/utils/format'
import { placeOf, placesFor } from '~/utils/places'

const sheet = useSheet()
const route = useRoute()
const { me, permissions, can, signOut } = useSession()
const prefs = usePrefs()
const { snapshot } = useSwitchboard(false)
const term = ref('')
const findEl = ref<{ inputRef?: HTMLInputElement | null } | null>(null)
const listEl = ref<HTMLElement | null>(null)
const toReview = ref(0)

const places = computed(() => placesFor(permissions.value))
const here = computed(() => placeOf(route.path)?.key ?? null)
const rows = computed(() => (snapshot.value ? boardRows(snapshot.value.lines, snapshot.value.handoffTray) : []))
const waiting = computed(() => rows.value.filter(r => r.lamp === 'urgent' || r.lamp === 'waiting').length)
const countOf = (key: string) => (key === 'lines' && waiting.value ? `${waiting.value} waiting for a person` : key === 'quality' && toReview.value ? `${toReview.value} to review` : null)

watch(() => sheet.open.value, async (open) => {
  if (!open) { term.value = ''; return }
  if (can('qa:read')) {
    try { toReview.value = (await api.qa.queue({ status: 'needs_review', pageSize: 1 })).total }
    catch { /* the count is optional */ }
  }
  if (sheet.find.value) setTimeout(() => findEl.value?.inputRef?.focus(), 60)
})
watch(() => route.fullPath, () => { sheet.open.value = false })

// Find: lines and this morning's claims that match, and a claim search.
const q = computed(() => term.value.trim().toLowerCase())
const foundLines = computed(() => (q.value ? rows.value.filter(r => `${r.callerLabel} ${r.lineLabel} ${r.place ?? ''}`.toLowerCase().includes(q.value)).slice(0, 4) : []))
const foundClaims = computed(() => (q.value ? (snapshot.value?.recentClaims ?? []).filter(c => `${c.claimNumber} ${c.holderName} ${c.lossPlace ?? ''}`.toLowerCase().includes(q.value)).slice(0, 4) : []))
function search() {
  const first = listEl.value?.querySelector<HTMLAnchorElement>('[data-found]')
  if (first) first.click()
  else if (q.value.length > 1 && can('claims:read')) void navigateTo(`/claims?q=${encodeURIComponent(term.value.trim())}`)
}

// Arrow keys move between every option in the sheet.
function onKey(e: KeyboardEvent) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
  const opts = [...(listEl.value?.querySelectorAll<HTMLElement>('[data-opt]') ?? [])]
  if (!opts.length) return
  e.preventDefault()
  const i = opts.indexOf(document.activeElement as HTMLElement)
  const n = e.key === 'ArrowDown' ? (i + 1) % opts.length : (i <= 0 ? opts.length - 1 : i - 1)
  opts[n]!.focus()
}

async function out() {
  sheet.open.value = false
  await signOut()
  await navigateTo('/sign-in')
}
const sizes = [{ label: 'Small', value: 's' }, { label: 'Medium', value: 'm' }, { label: 'Large', value: 'l' }]
</script>

<template>
  <UModal
    v-model:open="sheet.open.value" title="Where to?" description="Every question you can ask here, and Find"
    :ui="{ content: 'sheet-drop top-3 sm:top-5 translate-y-0 max-w-[980px] w-[calc(100vw-1.5rem)] max-h-[calc(100dvh-1.5rem)] overflow-y-auto', header: 'sr-only', body: 'p-0 sm:p-0' }"
  >
    <template #body>
      <div ref="listEl" class="sheet" @keydown="onKey">
        <form class="find" role="search" @submit.prevent="search">
          <UInput
            ref="findEl" v-model="term" size="xl" icon="i-lucide-search" class="w-full" autocomplete="off"
            placeholder="Find a caller, a claim number or a place" aria-label="Find a caller, a claim number or a place"
          />
        </form>

        <div v-if="q" class="found" aria-live="polite">
          <NuxtLink v-for="r in foundLines" :key="r.callId" :to="`/lines/${r.callId}`" class="fopt" data-opt data-found>
            <span class="fav">{{ initials(r.callerLabel) }}</span>
            <span><b>{{ r.callerLabel }}</b><small>{{ r.lineLabel }} · {{ r.stateWord }}</small></span>
          </NuxtLink>
          <NuxtLink v-for="c in foundClaims" :key="c.id" :to="`/claims/${c.id}`" class="fopt" data-opt data-found>
            <span class="fav doc"><UIcon name="i-lucide-file-text" class="size-4" /></span>
            <span><b>{{ c.holderName }}</b><small class="num">{{ c.claimNumber }} · {{ c.lossTypeLabel }}</small></span>
          </NuxtLink>
          <NuxtLink v-if="can('claims:read') && q.length > 1" :to="`/claims?q=${encodeURIComponent(term.trim())}`" class="fopt" data-opt>
            <span class="fav doc"><UIcon name="i-lucide-search" class="size-4" /></span>
            <span><b>Every claim matching “{{ term.trim() }}”</b><small>Search the claims register</small></span>
          </NuxtLink>
          <p v-if="!foundLines.length && !foundClaims.length && !can('claims:read')" class="none">
            Nothing on the lines matches that.
          </p>
        </div>

        <nav class="places" aria-label="Questions">
          <NuxtLink
            v-for="(p, i) in places" :key="p.key" :to="p.to" class="place" data-opt :style="{ '--i': i }"
            :aria-current="here === p.key ? 'page' : undefined"
          >
            <span class="pq round">{{ p.question }}</span>
            <span class="pmeta">
              <UIcon :name="p.icon" class="size-4" />{{ p.name }}
              <span v-if="countOf(p.key)" class="pcount num">{{ countOf(p.key) }}</span>
              <span v-if="here === p.key" class="here">You're here</span>
              <UKbd v-if="p.key2" :value="`G ${p.key2}`" class="kb" />
            </span>
          </NuxtLink>
        </nav>

        <section v-if="me" class="me" aria-label="You">
          <div class="who">
            <span class="av">{{ initials(me.user.fullName) }}</span>
            <span><b>{{ me.user.fullName }}</b><small>{{ me.membership?.roleLabel }} · {{ me.activeOrg?.name }}</small></span>
          </div>
          <div class="prefs">
            <USwitch :model-value="prefs.theme.value === 'dark'" label="Night line" @update:model-value="(v: boolean) => prefs.theme.value = v ? 'dark' : 'light'" />
            <USwitch v-model="prefs.reduceMotionSetting.value" label="Reduce motion" />
            <span class="cap">
              <span class="label">Caption size</span>
              <UTabs v-model="prefs.captions.value" :items="sizes" :content="false" size="xs" color="neutral" aria-label="Caption size" />
            </span>
          </div>
          <UButton color="neutral" variant="soft" icon="i-lucide-log-out" size="md" @click="out">
            Sign out
          </UButton>
        </section>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.sheet { padding: 22px 22px 18px; display: grid; gap: 18px; }
.find :deep(input) { font-size: 17px; }
.found { display: grid; gap: 6px; }
.fopt, .place { text-decoration: none; color: inherit; outline-offset: 2px; }
.fopt { display: flex; gap: 12px; align-items: center; padding: 8px 12px; border-radius: 18px; }
.fopt:hover, .fopt:focus-visible { background: var(--cv-jade-wash); }
.fopt b { display: block; font-weight: 600; }
.fopt small { color: var(--cv-muted); font-size: 13px; }
.fav { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-sand); color: var(--cv-caller); font-family: var(--font-round); font-weight: 900; font-size: 14px; flex: none; }
.fav.doc { background: var(--cv-sunk); color: var(--cv-muted); }
.none { margin: 0; color: var(--cv-muted); padding: 4px 12px; }

/* The places, as their questions. */
.places { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.place {
  display: grid; gap: 8px; padding: 18px 20px 16px; border-radius: 24px; background: var(--cv-bg);
  animation: rise 360ms var(--ease-tide) both; animation-delay: calc(var(--i) * 35ms);
  transition: background-color 160ms;
}
.place:hover, .place:focus-visible { background: var(--cv-jade-wash); }
.place[aria-current="page"] { background: var(--cv-jade-wash); box-shadow: inset 0 0 0 2px var(--cv-jade); }
.pq { font-size: 30px; line-height: 1.04; font-weight: 900; letter-spacing: -0.02em; text-shadow: 0 0.055em 0 var(--cv-cushion); }
.pmeta { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; color: var(--cv-muted); font-size: 14px; font-weight: 500; }
.pcount { padding: 2px 10px; border-radius: 999px; background: var(--cv-siu-wash); color: var(--cv-siu); font-size: 12.5px; font-weight: 600; }
.here { padding: 2px 10px; border-radius: 999px; background: var(--cv-jade); color: var(--cv-on-jade); font-size: 12.5px; font-weight: 600; }
.kb { margin-left: auto; }

.me { display: flex; align-items: center; gap: 14px 24px; flex-wrap: wrap; padding: 14px 16px; border-radius: 24px; background: var(--cv-sunk); }
.who { display: flex; align-items: center; gap: 10px; min-width: 220px; }
.who b { display: block; font-weight: 600; }
.who small { color: var(--cv-muted); font-size: 13px; }
.av { width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-person-wash); color: var(--cv-person); font-family: var(--font-round); font-weight: 900; flex: none; }
.prefs { display: flex; align-items: center; gap: 12px 22px; flex-wrap: wrap; flex: 1; }
.cap { display: inline-flex; align-items: center; gap: 8px; }
@media (max-width: 720px) {
  .sheet { padding: 16px 14px 14px; }
  .places { grid-template-columns: minmax(0, 1fr); }
  .pq { font-size: 24px; }
  .kb { display: none; }
}
</style>

<style>
/* Drop: the sheet falls from the heading with a little give (DESIGN.md §8). */
.sheet-drop[data-state="open"] { animation: sheet-drop var(--m-drop) var(--ease-spring); }
@keyframes sheet-drop { from { opacity: 0; transform: translateY(-18px) scale(.98); } to { opacity: 1; transform: none; } }
</style>
