<script setup lang="ts">
// The claim file (DESIGN.md §3) for the adjuster and special investigations. The crumb and the holder's name, then
// the claim card (a wallet pass: claim number, what, where, when, reported, assigned, route; What we heard, Change
// route, PDF). Then "Where does it go?": the verdict, three numbered reasons with their moments, likely size, the
// closer-look signs (folded, with the never-deny line) and Accept / Change. Then the recording, In short, and the
// answer sheet (photos under "Can you send photos?"). "What we heard" opens the conversation in a slide-over.
// Query flags: ?signs opens the signs, ?read opens the conversation, ?t= starts the recording at a second.
import type { Claim, Photo, Recording, RoutingDecision, Slot, Transcript, Turn } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, fmtDate, fmtDayShort, fmtTime, initials, money, zoneForRegion } from '~/utils/format'
import { lossIcon } from '~/utils/labels'
import { icon } from '~/utils/icons'
import { marksByTurn, slotByKey } from '~/utils/marks'
import { buildNotice, SECTION_STEP } from '~/utils/notice'
import { isSessionEnded } from '~/composables/useSession'

const route = useRoute()
const id = computed(() => String(route.params.claimId))
const { can, me } = useSession()
const links = useHeardLinks()
const listening = useListening()
const prefs = usePrefs()
const claim = ref<Claim | null>(null)
const transcript = ref<Transcript | null>(null)
const recording = ref<Recording | null>(null)
const decision = ref<RoutingDecision | null>(null)
const photos = ref<Photo[]>([])
const error = ref<string | null>(null)
const changing = ref(false)
const accepting = ref(false)
const reading = ref('read' in route.query)
const signsOpen = ref('signs' in route.query || can('siu:decide'))
const t = ref(0)
const startAt = computed(() => {
  const n = Number(route.query.t)
  return Number.isFinite(n) && n > 0 ? n : null
})
const rec = ref<{ seek: (s: number, play?: boolean) => void, playClip: (s: number) => void, toggle: () => void, playing: boolean } | null>(null)
useHead(() => ({ title: `${claim.value?.claimNumber ?? 'Claim'} · ClaimVoice` }))

async function load() {
  error.value = null
  try {
    claim.value = await api.claims.get(id.value)
    const [tr, rc, rd, ph] = await Promise.all([
      api.claims.transcript(id.value).catch(() => null),
      can('recordings:read') ? api.claims.recording(id.value).catch(() => null) : Promise.resolve(null),
      api.claims.routing(id.value).catch(() => null),
      api.claims.photos(id.value).catch(() => [] as Photo[]),
    ])
    transcript.value = tr
    recording.value = rc
    decision.value = rd
    photos.value = ph
    if ('signs' in route.query) setTimeout(() => document.getElementById('signs')?.scrollIntoView({ block: 'center' }), 400)
  }
  catch (e) {
    if (isSessionEnded(e)) return navigateTo({ path: '/sign-in', query: { next: route.fullPath } })
    error.value = (e as Error).message
  }
}
watch(id, load, { immediate: true })

const fr = computed(() => (claim.value?.language === 'fr' ? 'fr' : undefined))
const zone = computed(() => zoneForRegion(claim.value?.regionLabel === 'Colorado' ? 'US-CO' : claim.value?.regionLabel === 'Québec' ? 'CA-QC' : 'CA-AB'))
const lossWhen = computed(() => {
  const s = slotByKey(claim.value?.file, 'loss_time') ?? slotByKey(claim.value?.file, 'loss_date')
  return s?.display || (claim.value?.lossDate ? fmtDate(claim.value.lossDate) : '')
})
const reported = computed(() => (claim.value ? `${fmtDayShort(claim.value.reportedAt, zone.value).split(' ')[0]} ${fmtTime(claim.value.reportedAt, zone.value)}` : ''))
const caption = computed(() => {
  const c = claim.value
  if (!c) return ''
  const line = `${c.lossTypeLabel}${c.lossPlace ? ` in ${c.lossPlace.split(',').pop()!.trim()}` : ''}, reported ${reported.value}`
  return line.endsWith('.') ? line : `${line}.`
})

// The notice: sections 1–7 from the claim file (sections with nothing to show and nothing required are left out).
const sections = computed(() => {
  const file = claim.value?.file
  if (!file) return []
  return buildNotice({ ...file, sections: file.sections.filter(s => s.slots.some(x => x.display || x.required)) }, 7, true)
})
const hasPhotoStep = computed(() => sections.value.some(s => s.step === SECTION_STEP.photos))

// In short: the summary with heard phrases underlined, each a link to its moment on the tape.
const shortSegs = computed(() => {
  const s = claim.value?.inShort
  if (!s) return []
  const out: { text: string, at: number | null, link: boolean }[] = []
  let cur = 0
  for (const l of [...s.links].sort((a, b) => a.start - b.start)) {
    if (l.start < cur) continue
    if (l.start > cur) out.push({ text: s.text.slice(cur, l.start), at: null, link: false })
    out.push({ text: s.text.slice(l.start, l.end), at: l.atSeconds, link: true })
    cur = l.end
  }
  if (cur < s.text.length) out.push({ text: s.text.slice(cur), at: null, link: false })
  return out
})

// What we heard: the transcript follows the recording.
const turns = computed(() => transcript.value?.turns ?? [])
const signIds = computed(() => (decision.value?.signs ?? []).map(s => s.turnId).filter((x): x is string => !!x))
const marks = computed(() => marksByTurn(claim.value?.file))
const currentTurn = computed(() => {
  const ms = t.value * 1000
  let cur: Turn | null = null
  for (const x of turns.value) if (x.atMs <= ms + 50) cur = x
  return cur?.id ?? null
})
const txEl = ref<HTMLElement | null>(null)
watch([currentTurn, reading], async ([tid]) => {
  if (!reading.value || !tid) return
  await nextTick()
  txEl.value?.querySelector<HTMLElement>(`[data-turn="${tid}"]`)?.scrollIntoView({ block: 'center', behavior: prefs.reduceMotion.value ? 'auto' : 'smooth' })
})

function onActivate(slot: Slot) {
  if (slot.heardAtSeconds != null) rec.value?.playClip(slot.heardAtSeconds)
}
function printFile() { window.print() }
function seekTo(s: number) { rec.value?.seek(s, true) }
function onSpan(turnId: string, key: string) {
  const s = slotByKey(claim.value?.file, key)
  if (s?.span) {
    links.flash(s.span, false)
    nextTick(() => document.querySelector('.sheet .kv.linked')?.scrollIntoView({ block: 'nearest', behavior: prefs.reduceMotion.value ? 'auto' : 'smooth' }))
  }
  const turn = turns.value.find(x => x.id === turnId)
  if (turn) rec.value?.seek(turn.atMs / 1000)
}

// Where it goes.
const routeNote = computed(() => {
  const c = claim.value
  const d = decision.value
  if (!c || !d) return ''
  const who = c.assignedTo?.name ?? 'An adjuster'
  if (d.route === 'fast_track') return 'Paid from the photos and the policy. A person checks the amount before payment.'
  if (d.route === 'special_investigation') return `Special investigations reviews it first; ${who === 'An adjuster' ? 'an adjuster' : who} is told. It is never denied on a sign alone.`
  const signs = d.signs?.length ?? 0
  return c.siuOpen && signs ? `${who} handles the claim as normal. Special investigations reviews ${signs} detail${signs > 1 ? 's' : ''} alongside.` : `${who} handles the claim and calls the policyholder.`
})
const sizeDetail = computed(() => {
  const s = decision.value?.severity
  if (!s) return ''
  if (s.detail) return s.detail.charAt(0).toLowerCase() + s.detail.slice(1)
  return s.settleRange ? `claims like this usually settle at ${money(s.settleRange.low, s.settleRange.currency)} to ${money(s.settleRange.high, s.settleRange.currency)}` : ''
})
const sizeWord = computed(() => decision.value?.severity.label.replace(/^Likely size:\s*/i, '') ?? '')
const accepted = computed(() => decision.value?.acceptedBy ? `Accepted by ${decision.value.acceptedBy.name}` : null)

async function accept() {
  if (!claim.value) return
  accepting.value = true
  try { decision.value = await api.claims.acceptRoute(claim.value.id) }
  catch { listening.flash('That didn\'t save. Try again.') }
  accepting.value = false
}
function onChanged(d: RoutingDecision) {
  decision.value = d
  if (claim.value) claim.value = { ...claim.value, route: { route: d.route, label: d.routeLabel, decidedBy: 'person', topReason: d.override?.reason ?? '' } }
}
const photoLinkAt = computed(() => (claim.value?.file.sections.flatMap(s => s.slots).find(s => s.key === 'photo_link_sent_to')?.history[0]?.at) ?? null)
const callerFirst = computed(() => (claim.value ? firstName(claim.value.holderName) : ''))
function resendLink() { listening.flash(`Photo link sent to ${callerFirst.value} again.`) }
</script>

<template>
  <div class="claim">
    <PageHead :title="claim?.holderName ?? 'Claim'" :caption="caption" :back="{ to: '/claims', label: 'Claims' }">
      <UButton v-if="claim" color="neutral" variant="soft" icon="i-lucide-messages-square" :aria-pressed="reading" @click="reading = !reading">
        What we heard
      </UButton>
      <UButton v-if="can('claims:route') && decision" color="neutral" variant="soft" icon="i-lucide-arrow-left-right" class="hide-phone" @click="changing = true">
        Change route
      </UButton>
      <UButton v-if="claim" color="neutral" variant="outline" icon="i-lucide-printer" class="hide-phone" @click="printFile">
        Claim file PDF
      </UButton>
    </PageHead>

    <StateNote v-if="error" kind="error" title="We couldn't open this claim." :body="error" retry class="mb-6" @retry="load" />

    <!-- The claim card: a wallet pass -->
    <section v-if="claim" class="pass" :class="claim.route ? `r-${claim.route.route}` : ''" aria-label="The claim">
      <div class="strip">
        <CvMark :size="26" /><span>Larkspur Mutual · claim</span>
        <RouteTag v-if="claim.route" :route="claim.route.route" :label="claim.route.label" class="ml-auto" />
      </div>
      <div class="fields">
        <div class="f main">
          <span class="label">Claim number</span>
          <b class="round num">{{ claim.claimNumber }}</b>
        </div>
        <div class="f">
          <span class="label">What happened</span>
          <b><UIcon :name="icon(lossIcon(claim.lossType))" class="size-4" />{{ claim.lossTypeLabel }}</b>
        </div>
        <div class="f">
          <span class="label">Where</span>
          <b>{{ claim.lossPlace ?? claim.regionLabel }}</b>
        </div>
        <div v-if="lossWhen" class="f">
          <span class="label">When</span>
          <b>{{ lossWhen }}</b>
        </div>
        <div class="f">
          <span class="label">Reported</span>
          <b class="num">{{ reported }}</b>
        </div>
        <div v-if="claim.assignedTo" class="f">
          <span class="label">With</span>
          <b class="who"><span class="av">{{ initials(claim.assignedTo.name) }}</span>{{ claim.assignedTo.name }}{{ claim.assignedTo.id === me?.user.id ? ' (you)' : '' }}</b>
        </div>
        <div v-if="fr" class="f">
          <span class="label">Language</span>
          <b><UIcon name="i-lucide-languages" class="size-4" />Kept in French</b>
        </div>
      </div>
    </section>
    <USkeleton v-else-if="!error" class="h-44 rounded-[32px]" />

    <template v-if="claim">
      <!-- Where does it go? -->
      <section class="goes" aria-labelledby="goes-h">
        <h2 id="goes-h" class="pool-h">
          Where does {{ firstName(claim.holderName) }}'s claim go?
        </h2>
        <template v-if="decision">
          <RouteUnfurl :decision="decision" :siu-open="claim.siuOpen" @seek="seekTo">
            <template #note>
              <p class="routenote">
                {{ routeNote }}
              </p>
              <p v-if="decision.override" class="override">
                <UIcon name="i-lucide-arrow-left-right" class="size-4" />Changed by {{ decision.override.by.name }}: “{{ decision.override.reason }}”
              </p>
            </template>
          </RouteUnfurl>

          <div class="size">
            <span class="label">Likely size</span>
            <b class="round">{{ sizeWord }}</b>
            <span class="d">{{ sizeDetail }}</span>
          </div>

          <SignsList v-if="decision.signs && decision.signs.length" id="signs" v-model:open="signsOpen" :signs="decision.signs" :checked="decision.signsChecked" :statement="decision.statement" @seek="seekTo" />
          <p v-else class="never">
            <UIcon name="i-lucide-shield-check" class="size-4 shield" />{{ decision.statement }}
          </p>

          <div v-if="can('claims:route')" class="actions">
            <UButton v-if="!decision.acceptedBy" icon="i-lucide-check" size="xl" :loading="accepting" @click="accept">
              Accept the route
            </UButton>
            <CvTag v-else kind="fast" icon="check" lg>
              {{ accepted }}
            </CvTag>
            <UButton color="neutral" variant="soft" size="xl" icon="i-lucide-arrow-left-right" @click="changing = true">
              Change it, with a reason
            </UButton>
          </div>
          <p v-else-if="accepted" class="actions">
            <CvTag kind="fast" icon="check">
              {{ accepted }}
            </CvTag>
          </p>
        </template>
        <p v-else class="wait">
          The route appears here once the call's routing checks have run.
        </p>
      </section>

      <!-- The recording -->
      <section class="rec" aria-labelledby="rec-h">
        <h2 id="rec-h" class="pool-h">
          Hear the call
        </h2>
        <CallRecording
          v-if="recording" ref="rec" :recording="recording" :caller-label="callerFirst" :start-at="startAt" :turns="turns"
          label="The call's recording" @time="x => (t = x)"
        />
        <div v-else-if="can('recordings:read')" class="prep">
          <USkeleton class="size-16 rounded-full" />
          <p>The recording is being prepared. The words are ready now: open What we heard.</p>
        </div>
      </section>

      <!-- In short -->
      <section class="short" aria-labelledby="short-h">
        <div class="sq">
          <CvMark :size="30" />
          <h2 id="short-h">
            In short
          </h2>
          <small>Written from the call<template v-if="claim.inShort.checkedBy"> · checked by {{ firstName(claim.inShort.checkedBy.name) }}<template v-if="claim.inShort.checkedAt"> at {{ fmtTime(claim.inShort.checkedAt, zone).replace(/ [ap]\.m\./, '') }}</template></template></small>
        </div>
        <p class="stext">
          <template v-for="(s, i) in shortSegs" :key="i">
            <span
              v-if="s.link" role="button" :tabindex="s.at == null ? -1 : 0" class="ulink" :aria-label="`${s.text}, heard at ${fmtClock(s.at ?? 0)}`"
              @click="s.at != null && rec?.playClip(s.at)" @keydown.enter.prevent="s.at != null && rec?.playClip(s.at)" @keydown.space.prevent="s.at != null && rec?.playClip(s.at)"
            >{{ s.text }}</span><template v-else>
              {{ s.text }}
            </template>
          </template>
        </p>
        <p v-if="claim.descriptionEn && claim.language === 'fr'" class="en">
          {{ claim.descriptionEn }}
        </p>
      </section>

      <!-- The answers -->
      <AnswerSheet class="answers" title="What the caller told us" :sections="sections" :step="7" ended :language="claim.language" :reference="claim.claimNumber" @activate="onActivate">
        <template #step-5>
          <PhotoTiles :photos="photos" :link-sent-at="photoLinkAt" :can-resend="can('claims:edit')" @resend="resendLink" />
        </template>
        <template v-if="!hasPhotoStep" #after>
          <PhotoTiles :photos="photos" :link-sent-at="photoLinkAt" :can-resend="can('claims:edit')" @resend="resendLink" />
        </template>
      </AnswerSheet>
    </template>
    <AnswerSheet v-else-if="!error" class="answers" :sections="[]" :step="7" ended loading />

    <!-- What we heard: the conversation as bubbles, following the recording -->
    <USlideover
      v-model:open="reading" side="right" title="What we heard" :description="recording?.available ? 'Follows the recording. Press a time to play from there.' : 'Notes from the call'"
      :modal="false" :overlay="false" :content="{ onInteractOutside: (e: Event) => e.preventDefault() }" :ui="{ content: 'max-w-xl', body: 'px-4 sm:px-5' }"
    >
      <template #body>
        <p v-if="transcript && !transcript.retained" class="refused">
          <UIcon name="i-lucide-shield-check" class="size-4" />{{ transcript.notice }}
        </p>
        <div ref="txEl">
          <Conversation
            :turns="turns" :marks="marks" :caller-label="claim?.holderName" :current-id="currentTurn" :sign-ids="signIds"
            :seekable="!!recording?.available" label="Transcript" @seek="seekTo" @span="onSpan"
          />
        </div>
        <p v-if="!turns.length" class="refused">
          Nothing was written down from this call.
        </p>
      </template>
      <template v-if="recording?.available" #footer>
        <div class="flex items-center gap-3 w-full">
          <UButton :icon="rec?.playing ? 'i-lucide-pause' : 'i-lucide-play'" color="primary" class="rounded-full" :aria-label="rec?.playing ? 'Pause' : `Play from ${fmtClock(t)}`" @click="rec?.toggle()" />
          <time class="num font-semibold">{{ fmtClock(t) }}</time>
          <UButton color="neutral" variant="ghost" class="ml-auto" @click="reading = false">
            Back to the claim
          </UButton>
        </div>
      </template>
    </USlideover>

    <ChangeRouteSheet v-if="claim && decision" :open="changing" :claim-id="claim.id" :claim-number="claim.claimNumber" :current="decision.route" @close="changing = false" @changed="onChanged" />
  </div>
</template>

<style scoped>
/* The claim card, a wallet pass. */
.pass { border-radius: 32px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); overflow: hidden; }
.strip { display: flex; align-items: center; gap: 10px; padding: 12px 22px; background: var(--cv-jade-wash); font-size: 13.5px; font-weight: 500; color: var(--cv-jade-ink); }
.r-adjuster .strip { background: var(--cv-adj-wash); color: var(--cv-adj); }
.r-special_investigation .strip { background: var(--cv-siu-wash); color: var(--cv-siu); }
.fields { display: flex; flex-wrap: wrap; gap: 18px 36px; padding: 20px 24px 22px; align-items: flex-end; }
.f { display: grid; gap: 4px; min-width: 0; }
.f b { display: inline-flex; align-items: center; gap: 7px; font-weight: 500; font-size: 16px; }
.f.main b { font-size: 40px; line-height: 1; font-weight: 900; letter-spacing: -0.02em; }
.who .av { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--cv-person-wash); color: var(--cv-person); font-family: var(--font-round); font-weight: 900; font-size: 11px; }

/* Where does it go? */
.goes { margin-top: 36px; display: grid; gap: 16px; padding: 26px 28px; border-radius: 32px; background: linear-gradient(180deg, var(--cv-jade-wash), color-mix(in srgb, var(--cv-jade-wash) 25%, var(--cv-bg)) 80%); }
.r-adjuster ~ .goes, .claim:has(.r-adjuster) .goes { background: linear-gradient(180deg, var(--cv-adj-wash), color-mix(in srgb, var(--cv-adj-wash) 25%, var(--cv-bg)) 80%); }
.claim:has(.r-special_investigation) .goes { background: linear-gradient(180deg, var(--cv-siu-wash), color-mix(in srgb, var(--cv-siu-wash) 25%, var(--cv-bg)) 80%); }
.routenote { margin: 12px 0 0; font-size: 18px; line-height: 1.4; max-width: 64ch; }
.override { display: flex; gap: 6px; align-items: center; font-size: 14px; font-weight: 500; margin: 6px 0 0; }
.size { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 14px; }
.size b { font-size: 26px; font-weight: 900; letter-spacing: -0.02em; }
.size .d { color: var(--cv-muted); font-size: 14.5px; }
.never { display: flex; gap: 8px; align-items: flex-start; margin: 0; padding: 12px 16px; border-radius: 20px; background: var(--cv-surface); font-size: 14px; font-weight: 500; }
.never .shield { color: var(--cv-siu); margin-top: 2px; flex: none; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 4px 0 0; }
.wait { margin: 0; color: var(--cv-muted); }

.rec { margin-top: 40px; display: grid; gap: 14px; }
.prep { display: flex; gap: 14px; align-items: center; padding: 20px; border-radius: 28px; background: var(--cv-surface); color: var(--cv-muted); }
.prep p { margin: 0; }

/* In short: ClaimVoice's summary, as its own bubble. */
.short { margin-top: 40px; display: grid; gap: 10px; }
.sq { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sq h2 { font-size: 26px; font-weight: 900; }
.sq small { color: var(--cv-muted); font-size: 13px; }
.stext { margin: 0; max-width: 72ch; padding: 18px 22px; border-radius: 6px 26px 26px 26px; background: var(--cv-jade-wash); font-size: calc(19px * var(--cv-caption-scale)); line-height: 1.5; }
.ulink { text-decoration: underline; text-decoration-color: var(--cv-jade); text-decoration-thickness: 2px; text-underline-offset: 4px; cursor: pointer; border-radius: 6px; }
.ulink:hover, .ulink:focus-visible { background: var(--cv-seaglass); }
.en { display: block; color: var(--cv-muted); font-size: 14px; margin: 0; max-width: 72ch; }
.answers { margin-top: 44px; }
.refused { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 500; margin: 0 0 12px; }

@media (max-width: 720px) {
  .fields { padding: 16px 18px 18px; gap: 14px 24px; }
  .f.main b { font-size: 30px; }
  .goes { padding: 20px 16px; border-radius: 26px; }
  .routenote { font-size: 16px; }
  .stext { font-size: calc(17px * var(--cv-caption-scale)); padding: 14px 16px; }
}
@media print {
  .actions, .claim :deep(.pagehead .ctl), .claim :deep(.crumb) { display: none; }
}
</style>
