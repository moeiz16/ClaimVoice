<script setup lang="ts">
// The claim file (DESIGN.md §5.4) for the adjuster and special investigations. The slate (holder, claim number, loss
// and times; assigned person, Change route, Claim file PDF), then the tape: the recording with the current turn
// written on it. Then section 8 first, "Where it goes": the route, one sentence on who does what, three numbered
// reasons with their moments, likely size, the closer-look signs (folded, with the never-deny note) and Accept route /
// Change with a reason. Then the loss notice: "In short" as its remarks, sections 1–7 with margin notes, photos in
// section 5. "What we heard" opens the whole transcript from the left, following the recording.
// Query flags: ?signs opens the signs, ?read opens the transcript, ?t= starts the tape at a second.
import type { Claim, Photo, Recording, RoutingDecision, Slot, Transcript, Turn } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, fmtDate, fmtDayShort, fmtTime, money, zoneForRegion } from '~/utils/format'
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
const caption = computed(() => {
  const c = claim.value
  if (!c) return ''
  return `${c.claimNumber} · ${c.lossTypeLabel}${c.lossPlace ? `, ${c.lossPlace.split(',').pop()!.trim()}` : ''}${lossWhen.value ? ` · ${lossWhen.value}` : ''} · reported ${fmtDayShort(c.reportedAt, zone.value).split(' ')[0]} ${fmtTime(c.reportedAt, zone.value)}`
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
const signTurns = computed(() => new Set((decision.value?.signs ?? []).map(s => s.turnId).filter(Boolean)))
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
const speakerOf = (x: Turn) => (x.speaker === 'whisper' ? 'Whisper, ClaimVoice only' : x.speaker === 'caller' ? firstName(x.speakerLabel) : x.speakerLabel)

function onActivate(slot: Slot) {
  if (slot.heardAtSeconds != null) rec.value?.playClip(slot.heardAtSeconds)
}
function printFile() { window.print() }
function seekTo(s: number) { rec.value?.seek(s, true) }
function onSpan(turnId: string, key: string) {
  const s = slotByKey(claim.value?.file, key)
  if (s?.span) {
    links.flash(s.span, false)
    nextTick(() => document.querySelector('.notice .box.linked')?.scrollIntoView({ block: 'nearest', behavior: prefs.reduceMotion.value ? 'auto' : 'smooth' }))
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
    <Slate :title="claim?.holderName ?? 'Claim'" :caption="caption" :back="{ to: '/claims', label: 'Claims' }">
      <CvTag v-if="claim?.assignedTo" kind="person" icon="person" lg class="hide-phone">
        {{ claim.assignedTo.name }}{{ claim.assignedTo.id === me?.user.id ? ' (you)' : '' }}
      </CvTag>
      <UButton v-if="claim" color="neutral" variant="soft" icon="i-lucide-text" :aria-pressed="reading" @click="reading = !reading">
        What we heard
      </UButton>
      <UButton v-if="can('claims:route') && decision" color="neutral" variant="soft" icon="i-lucide-arrow-left-right" class="hide-phone" @click="changing = true">
        Change route
      </UButton>
      <UButton v-if="claim" color="neutral" icon="i-lucide-file-text" class="hide-phone" @click="printFile">
        Claim file PDF
      </UButton>
    </Slate>

    <StateNote v-if="error" kind="error" title="We couldn't open this claim." :body="error" retry class="m-4 sm:mx-8" @retry="load" />

    <!-- The tape -->
    <CallRecording
      v-if="recording" ref="rec" :recording="recording" :caller-label="callerFirst" :start-at="startAt" :turns="turns"
      label="The call's recording" @time="x => (t = x)"
    />
    <Tape v-else-if="claim && can('recordings:read')" label="The call's recording">
      <template #key>
        <USkeleton class="size-14 rounded-full" />
      </template>
      <div class="prep">
        <USkeleton class="h-11 w-56 flex-none" />
        <p>The recording is being prepared. The transcript is ready now.</p>
      </div>
    </Tape>
    <Tape v-else-if="!claim && !error" label="Loading the recording">
      <template #key>
        <USkeleton class="size-14 rounded-full" />
      </template>
      <USkeleton class="h-full w-full" />
    </Tape>

    <template v-if="claim">
      <!-- 8 · Where it goes, first -->
      <section class="goes" aria-labelledby="goes-h">
        <header class="ghead">
          <span class="no num" aria-hidden="true">8</span>
          <h2 id="goes-h">
            Where it goes
          </h2>
        </header>

        <template v-if="decision">
          <RouteUnfurl :decision="decision" :siu-open="claim.siuOpen" @seek="seekTo">
            <template #note>
              <p class="routenote voice">
                {{ routeNote }}
              </p>
              <p v-if="decision.override" class="override">
                <UIcon name="i-lucide-arrow-left-right" class="size-4" />Changed by {{ decision.override.by.name }}: “{{ decision.override.reason }}”
              </p>
            </template>
          </RouteUnfurl>

          <div class="size">
            <span class="k">Likely size</span>
            <b class="voice">{{ sizeWord }}</b>
            <span class="d">{{ sizeDetail }}</span>
          </div>

          <SignsList v-if="decision.signs && decision.signs.length" id="signs" v-model:open="signsOpen" :signs="decision.signs" :checked="decision.signsChecked" :statement="decision.statement" @seek="seekTo" />
          <p v-else class="never">
            <UIcon name="i-lucide-shield-check" class="size-4 shield" />{{ decision.statement }}
          </p>

          <div v-if="can('claims:route')" class="actions">
            <UButton v-if="!decision.acceptedBy" icon="i-lucide-check" :loading="accepting" @click="accept">
              Accept route
            </UButton>
            <CvTag v-else kind="fast" icon="check" lg>
              {{ accepted }}
            </CvTag>
            <UButton color="neutral" variant="soft" icon="i-lucide-arrow-left-right" @click="changing = true">
              Change with a reason
            </UButton>
          </div>
          <p v-else-if="accepted" class="actions">
            <CvTag kind="fast" icon="check">
              {{ accepted }}
            </CvTag>
          </p>
        </template>
        <p v-else class="routenote">
          The route appears here once the call's routing checks have run.
        </p>
      </section>

      <!-- 1–7 · The loss notice -->
      <LossNotice
        :sections="sections" :step="7" ended :turns="turns" :language="claim.language" :reference="claim.claimNumber"
        @activate="onActivate"
      >
        <template #head>
          <CvTag v-if="fr" kind="orchid" icon="lang">
            Kept in French · English shown for staff
          </CvTag>
        </template>
        <template #before>
          <div class="remarks">
            <div class="rhead">
              <span class="k">Remarks · In short</span>
              <small>Written from the call<template v-if="claim.inShort.checkedBy"> · checked by {{ firstName(claim.inShort.checkedBy.name) }}<template v-if="claim.inShort.checkedAt"> at {{ fmtTime(claim.inShort.checkedAt, zone).replace(/ [ap]\.m\./, '') }}</template></template></small>
            </div>
            <p class="short">
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
          </div>
        </template>
        <template #step-5>
          <PhotoTiles :photos="photos" :link-sent-at="photoLinkAt" :can-resend="can('claims:edit')" @resend="resendLink" />
        </template>
        <template v-if="!hasPhotoStep" #after>
          <PhotoTiles :photos="photos" :link-sent-at="photoLinkAt" :can-resend="can('claims:edit')" @resend="resendLink" />
        </template>
      </LossNotice>
    </template>
    <LossNotice v-else-if="!error" :sections="[]" :step="7" ended loading />

    <!-- What we heard: the whole conversation, from the left, following the recording -->
    <USlideover
      v-model:open="reading" side="left" title="What we heard" :description="recording?.available ? 'Follows the recording. Click a time to play from there.' : 'Notes from the call'"
      :modal="false" :overlay="false" :content="{ onInteractOutside: (e: Event) => e.preventDefault() }" :ui="{ content: 'max-w-lg', body: 'p-0 sm:p-0' }"
    >
      <template #body>
        <p v-if="transcript && !transcript.retained" class="refused">
          <UIcon name="i-lucide-shield-check" class="size-4" />{{ transcript.notice }}
        </p>
        <ol ref="txEl" class="tx" aria-label="Transcript">
          <li v-for="x in turns" :key="x.id" class="t" :data-turn="x.id" :class="[x.speaker, { on: x.id === currentTurn, sign: signTurns.has(x.id) }]" :aria-current="x.id === currentTurn ? 'true' : undefined">
            <button type="button" class="tm num" :aria-label="`Play from ${fmtClock(x.atMs / 1000)}`" :disabled="!recording?.available" @click="seekTo(x.atMs / 1000)">
              {{ fmtClock(x.atMs / 1000) }}
            </button>
            <div>
              <b>{{ speakerOf(x) }}</b>
              <p :lang="x.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="x.text" :turn-id="x.id" :marks="marks[x.id]" @span="k => onSpan(x.id, k)" />
              </p>
              <span v-if="x.textEn" class="en">{{ x.textEn }}</span>
              <CvTag v-if="signTurns.has(x.id)" kind="siu" icon="look" class="signtag">
                A sign worth a closer look
              </CvTag>
            </div>
          </li>
        </ol>
        <p v-if="!turns.length" class="refused">
          Nothing was written down from this call.
        </p>
      </template>
      <template v-if="recording?.available" #footer>
        <div class="flex items-center gap-3">
          <UButton :icon="rec?.playing ? 'i-lucide-pause' : 'i-lucide-play'" color="primary" :aria-label="rec?.playing ? 'Pause' : `Play from ${fmtClock(t)}`" @click="rec?.toggle()" />
          <time class="num font-semibold">{{ fmtClock(t) }}</time>
          <UButton color="neutral" variant="ghost" class="ml-auto" @click="reading = false">
            Back to the notice
          </UButton>
        </div>
      </template>
    </USlideover>

    <ChangeRouteSheet v-if="claim && decision" :open="changing" :claim-id="claim.id" :claim-number="claim.claimNumber" :current="decision.route" @close="changing = false" @changed="onChanged" />
  </div>
</template>

<style scoped>
.prep { height: 100%; display: flex; gap: 14px; align-items: center; color: var(--cv-muted); font-weight: 600; }
.prep p { margin: 0; }

/* 8 · Where it goes: a full-width ruled band */
.goes { padding: 20px 32px 22px; border-bottom: 1px solid var(--cv-rule); display: grid; gap: 14px; }
.ghead { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ghead h2 { font-size: 22px; font-weight: 680; }
.no {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 720; font-size: 15px;
  background: var(--cv-ink); color: var(--cv-bg);
}
.routenote { margin: 0; font-size: 18px; font-weight: 560; line-height: 1.35; font-variation-settings: "FLAR" 60; max-width: 72ch; }
.goes > .routenote { font-family: var(--font-sans); font-size: 15px; color: var(--cv-muted); }
.override { display: flex; gap: 6px; align-items: center; font-size: 14px; font-weight: 600; margin: 6px 0 0; }
.size { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 14px; padding: 2px 0; }
.size .k { font-size: 13px; font-weight: 650; color: var(--cv-muted); }
.size b { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
.size .d { color: var(--cv-muted); font-size: 14.5px; }
.never { display: flex; gap: 8px; align-items: flex-start; margin: 0; padding: 10px 12px; border-radius: 6px; background: var(--cv-siu-wash); font-size: 14px; font-weight: 600; }
.never .shield { color: var(--cv-siu); margin-top: 2px; flex: none; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 0; }

/* Remarks · In short, the notice's first box */
.remarks { border: 1px solid var(--cv-rule); border-radius: 6px; background: var(--cv-surface); padding: 10px 14px 14px; }
.rhead { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.rhead .k { font-size: 12px; font-weight: 650; color: var(--cv-muted); }
.rhead small { margin-left: auto; font-size: 12.5px; color: var(--cv-muted); font-weight: 600; }
.short {
  font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: calc(19px * var(--cv-caption-scale));
  font-weight: 520; line-height: 1.42; letter-spacing: -0.005em; margin: 6px 0 0; max-width: 88ch;
}
.ulink { text-decoration: underline; text-decoration-color: var(--cv-orchid); text-decoration-thickness: 2px; text-underline-offset: 4px; cursor: pointer; border-radius: 2px; }
.ulink:hover, .ulink:focus-visible { background: var(--cv-orchid-wash); }
.en { display: block; color: var(--cv-muted); font-size: 13.5px; margin-top: 4px; }
.remarks .en { margin-top: 8px; }

/* What we heard */
.tx { list-style: none; margin: 0; padding: 6px 0; display: grid; }
.t { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 8px; padding: 8px 16px; border-left: 3px solid transparent; font-size: calc(15.5px * var(--cv-caption-scale)); line-height: 1.55; transition: background-color 200ms; }
.tm { border: 0; background: none; color: var(--cv-muted); font-size: 12px; font-weight: 650; padding: 4px 0 0; text-align: left; align-self: start; cursor: pointer; }
.tm:hover:not(:disabled) { color: var(--cv-orchid-ink); }
.tm:disabled { cursor: default; }
.t b { display: block; font-size: 12px; color: var(--cv-muted); line-height: 1.3; }
.t p { margin: 0; }
.t.caller p { color: var(--cv-caller); }
.t.whisper p { color: var(--cv-person); }
.t.on { background: var(--cv-orchid-wash); border-left-color: var(--cv-orchid); }
.t.sign { border-left-color: var(--cv-siu); }
.signtag { margin-top: 6px; }
.refused { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; padding: 12px 16px 0; margin: 0; }
:global(.reduce-motion) .t { transition: none; }

@media (max-width: 720px) {
  .goes { padding: 16px 16px 18px; }
  .routenote { font-size: 16.5px; }
  .rhead small { margin-left: 0; }
}
@media print {
  .actions, .claim :deep(.slate .ctl) { display: none; }
}
</style>
