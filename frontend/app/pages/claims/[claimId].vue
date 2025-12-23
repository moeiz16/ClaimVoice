<script setup lang="ts">
// The claim file (DESIGN.md §5.4): the recording band, then In short (summary and fields with their sources), What
// we heard (the transcript following the recording), and Where it goes (route, reasons, likely size, closer-look
// signs with the never-deny note, photos, Accept route / Change with a reason). Query flag ?signs scrolls to signs.
import type { Claim, Photo, Recording, RoutingDecision, Slot, Transcript, Turn } from '~/types/api'
import { api } from '~/utils/api'
import { firstName, fmtClock, fmtDate, fmtDayShort, fmtTime, money, zoneForRegion } from '~/utils/format'
import { marksByTurn, slotByKey } from '~/utils/marks'
import { sectionIcon } from '~/utils/labels'
import { isSessionEnded } from '~/composables/useSession'

const route = useRoute()
const id = computed(() => String(route.params.claimId))
const { can, me } = useSession()
const links = useHeardLinks()
const claim = ref<Claim | null>(null)
const transcript = ref<Transcript | null>(null)
const recording = ref<Recording | null>(null)
const decision = ref<RoutingDecision | null>(null)
const photos = ref<Photo[]>([])
const error = ref<string | null>(null)
const changing = ref(false)
const accepting = ref(false)
const t = ref(0)
const rec = ref<{ seek: (s: number, play?: boolean) => void, playClip: (s: number) => void } | null>(null)
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

// In short: the summary with heard phrases underlined, each a link to its moment.
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
const sections = computed(() => (claim.value?.file.sections ?? []).filter(s => s.slots.some(x => x.display || x.required)))

// The transcript follows the recording.
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
watch(currentTurn, async (tid) => {
  await nextTick()
  const el = txEl.value?.querySelector<HTMLElement>(`[data-turn="${tid}"]`)
  if (el && txEl.value) txEl.value.scrollTo({ top: el.offsetTop - txEl.value.clientHeight / 3, behavior: usePrefs().reduceMotion.value ? 'auto' : 'smooth' })
})

function clip(slot: Slot) {
  if (slot.span) links.flash(slot.span)
  if (slot.heardAtSeconds != null) rec.value?.playClip(slot.heardAtSeconds)
}
function printFile() { window.print() }
function seekTo(s: number) { rec.value?.seek(s, true) }
function onSpan(turnId: string, key: string) {
  const s = slotByKey(claim.value?.file, key)
  if (s) { links.flash(s.span, false); document.getElementById(`field-${s.key}`)?.scrollIntoView({ block: 'nearest' }) }
  const turn = turns.value.find(x => x.id === turnId)
  if (turn) rec.value?.seek(turn.atMs / 1000)
}

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
  catch { useListening().flash('That didn\'t save. Try again.') }
  accepting.value = false
}
function onChanged(d: RoutingDecision) {
  decision.value = d
  if (claim.value) claim.value = { ...claim.value, route: { route: d.route, label: d.routeLabel, decidedBy: 'person', topReason: d.override?.reason ?? '' } }
}
const photoLinkAt = computed(() => (claim.value?.file.sections.flatMap(s => s.slots).find(s => s.key === 'photo_link_sent_to')?.history[0]?.at) ?? null)
const callerFirst = computed(() => (claim.value ? firstName(claim.value.holderName) : ''))
</script>

<template>
  <div class="claim">
    <PageHeader :title="claim?.holderName ?? 'Claim'" :caption="caption" :back="{ to: '/claims', label: 'Claims' }">
      <CvTag v-if="claim?.assignedTo" kind="adj" icon="person" lg class="hide-phone">
        {{ claim.assignedTo.name }}{{ claim.assignedTo.id === me?.user.id ? ' (you)' : '' }}
      </CvTag>
      <button v-if="can('claims:route') && decision" class="btn soft sm hide-phone" type="button" @click="changing = true">
        <CvIcon name="swap" size="s" />Change route
      </button>
      <button class="btn ink sm hide-phone" type="button" @click="printFile">
        <CvIcon name="doc" size="s" />Claim file PDF
      </button>
    </PageHeader>

    <StateNote v-if="error" kind="error" title="We couldn't open this claim." :body="error" retry class="wrap" @retry="load" />

    <div class="wrap">
      <CallRecording v-if="recording" ref="rec" :recording="recording" :caller-label="callerFirst" :start-at="null" @time="x => (t = x)" />
      <div v-else-if="claim && can('recordings:read')" class="rec-wait">
        <span class="skeleton" />The recording is being prepared. The transcript is ready now.
      </div>
    </div>

    <main v-if="claim" class="cols">
      <section class="card scrollcol" aria-labelledby="short-h">
        <h2 id="short-h">
          In short <small>Written from the call<template v-if="claim.inShort.checkedBy"> · checked by {{ firstName(claim.inShort.checkedBy.name) }}<template v-if="claim.inShort.checkedAt"> at {{ fmtTime(claim.inShort.checkedAt, zone).replace(/ [ap]\.m\./, '') }}</template></template></small>
        </h2>
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
        <template v-for="sec in sections" :key="sec.key">
          <div class="group-label grp">
            <CvIcon :name="sectionIcon(sec.key)" size="s" />{{ sec.label }}
          </div>
          <dl class="kv">
            <template v-for="s in sec.slots" :key="s.key">
              <dt :id="`field-${s.key}`">
                {{ s.label }}
              </dt>
              <dd>
                <HeardValue :field="s" :linked="links.isActive(s.span)" @hover="on => links.hover(on ? s.span : null)" @activate="clip(s)" />
              </dd>
            </template>
          </dl>
        </template>
      </section>

      <section class="card scrollcol" aria-labelledby="heard-h">
        <h2 id="heard-h">
          What we heard <small>{{ recording?.available ? 'Follows the recording' : 'Notes from the call' }}</small>
        </h2>
        <p v-if="transcript && !transcript.retained" class="refused">
          <CvIcon name="shield" size="s" />{{ transcript.notice }}
        </p>
        <div ref="txEl" class="tx">
          <div v-for="x in turns" :key="x.id" class="t" :data-turn="x.id" :class="[x.speaker, { on: x.id === currentTurn, sign: signTurns.has(x.id) }]">
            <button type="button" class="tm num" :aria-label="`Play from ${fmtClock(x.atMs / 1000)}`" @click="seekTo(x.atMs / 1000)">
              {{ fmtClock(x.atMs / 1000) }}
            </button>
            <div>
              <b>{{ x.speaker === 'whisper' ? 'Whisper, ClaimVoice only' : x.speaker === 'caller' ? firstName(x.speakerLabel) : x.speakerLabel }}</b>
              <p :lang="x.language === 'fr' ? 'fr' : undefined">
                <TranscriptText :text="x.text" :turn-id="x.id" :marks="marks[x.id]" @span="k => onSpan(x.id, k)" />
              </p>
              <span v-if="x.textEn" class="en">{{ x.textEn }}</span>
              <span v-if="signTurns.has(x.id)" class="tag siu signtag"><CvIcon name="look" size="s" />A sign worth a closer look</span>
            </div>
          </div>
        </div>
      </section>

      <section class="card tint scrollcol" aria-labelledby="goes-h">
        <h2 id="goes-h">
          Where it goes
        </h2>
        <template v-if="decision">
          <RouteUnfurl :decision="decision" :siu-open="claim.siuOpen" @seek="seekTo">
            <template #note>
              <p class="routenote">
                {{ routeNote }}
              </p>
              <p v-if="decision.override" class="override">
                <CvIcon name="swap" size="s" />Changed by {{ decision.override.by.name }}: “{{ decision.override.reason }}”
              </p>
            </template>
          </RouteUnfurl>
          <div class="size">
            <span class="k">Likely size</span><b>{{ sizeWord }}</b><span class="d">{{ sizeDetail }}</span>
          </div>
          <SignsList v-if="decision.signs && decision.signs.length" id="signs" :signs="decision.signs" :checked="decision.signsChecked" :statement="decision.statement" @seek="seekTo" />
          <p v-else class="never">
            <CvIcon name="shield" size="s" />{{ decision.statement }}
          </p>
        </template>
        <p v-else class="routenote">
          The route appears here once the call's routing checks have run.
        </p>
        <PhotoTiles :photos="photos" :link-sent-at="photoLinkAt" />
        <div v-if="decision && can('claims:route')" class="actions">
          <button v-if="!decision.acceptedBy" class="btn primary sm" type="button" :disabled="accepting" @click="accept">
            Accept route
          </button>
          <span v-else class="tag fast"><CvIcon name="check" size="s" />{{ accepted }}</span>
          <button class="btn soft sm on-sunk" type="button" @click="changing = true">
            Change with a reason
          </button>
        </div>
      </section>
    </main>
    <div v-else-if="!error" class="cols" aria-busy="true">
      <span v-for="n in 3" :key="n" class="skeleton" style="height: 420px; border-radius: 28px" />
    </div>

    <ChangeRouteSheet v-if="claim && decision" :open="changing" :claim-id="claim.id" :claim-number="claim.claimNumber" :current="decision.route" @close="changing = false" @changed="onChanged" />
  </div>
</template>

<style scoped>
.wrap { margin: 0 32px; }
.rec-wait { background: var(--cv-surface); border-radius: 28px; padding: 22px; display: flex; gap: 14px; align-items: center; color: var(--cv-muted); font-weight: 600; }
.rec-wait .skeleton { width: 220px; height: 40px; flex: none; }
.cols { display: grid; grid-template-columns: 1.05fr 1fr 1fr; gap: 16px; margin: 16px 32px 0; align-items: start; }
.card { padding: 18px 20px; }
.scrollcol { max-height: calc(100dvh - 72px - 240px - 110px); min-height: 460px; overflow: auto; position: relative; scrollbar-width: thin; }
h2 { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
h2 small { margin-left: auto; font-family: var(--font-sans); font-size: 12.5px; color: var(--cv-muted); font-weight: 650; letter-spacing: 0; }
.short { font-family: var(--font-display); font-size: calc(19px * var(--cv-caption-scale)); font-weight: 500; line-height: 1.38; letter-spacing: -0.01em; margin: 10px 0 14px; }
.ulink { text-decoration: underline; text-decoration-color: var(--cv-orchid); text-decoration-thickness: 2px; text-underline-offset: 4px; cursor: pointer; border-radius: 2px; }
.ulink:hover { background: var(--cv-orchid-wash); }
.en { display: block; color: var(--cv-muted); font-size: 13.5px; margin-top: 2px; }
.grp { margin: 14px 0 6px; }
.kv { display: grid; grid-template-columns: 112px 1fr; gap: 7px 10px; font-size: 14px; align-items: center; margin: 0; }
.kv dt { color: var(--cv-muted); font-size: 13px; }
.kv dd { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.kv :deep(.heard) { min-height: 28px; font-size: 13.5px; padding: 2px 5px 2px 11px; }
.kv :deep(.heard .at) { height: 21px; font-size: 11.5px; }
.tx { display: flex; flex-direction: column; gap: 4px; margin-top: 10px; }
.t { display: grid; grid-template-columns: 40px 1fr; gap: 8px; padding: 7px 10px; border-radius: 14px; font-size: calc(14.5px * var(--cv-caption-scale)); transition: background-color 200ms; }
.tm { border: 0; background: none; color: var(--cv-faint); font-size: 12px; font-weight: 650; padding: 2px 0 0; text-align: left; align-self: start; }
.tm:hover { color: var(--cv-orchid-ink); }
.t b { display: block; font-size: 12px; color: var(--cv-muted); }
.t.caller p { color: var(--cv-caller); }
.t.whisper p { color: var(--cv-person); }
.t p { margin: 0; }
.t.on { background: var(--cv-orchid-wash); }
.signtag { margin-top: 6px; height: 24px; font-size: 12px; }
.refused { display: flex; gap: 6px; align-items: center; color: var(--cv-muted); font-weight: 600; }
.routenote { color: var(--cv-muted); font-size: 14px; margin: 0 0 12px; }
.override { display: flex; gap: 6px; align-items: center; font-size: 13.5px; font-weight: 600; margin: -6px 0 12px; }
.size { display: grid; grid-template-columns: auto 1fr; align-items: baseline; column-gap: 12px; margin-top: 14px; font-size: 13.5px; }
.size .k { grid-column: 1 / -1; font-size: 12.5px; font-weight: 750; color: var(--cv-muted); }
.size b { font-family: var(--font-display); font-size: 24px; letter-spacing: -0.02em; }
.size .d { color: var(--cv-muted); }
.never { display: flex; gap: 8px; align-items: flex-start; margin: 14px 0 0; padding: 10px 12px; border-radius: 14px; background: var(--cv-surface); font-size: 13.5px; font-weight: 600; }
.never :deep(svg) { color: var(--cv-siu); margin-top: 2px; }
.actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; align-items: center; }
@media (max-width: 1200px) { .cols { grid-template-columns: 1fr 1fr; } .cols > :last-child { grid-column: 1 / -1; } .scrollcol { max-height: none; } }
@media (max-width: 720px) {
  .wrap { margin: 0 16px; }
  .cols { grid-template-columns: 1fr; margin: 12px 16px 0; }
  .cols > :last-child { grid-column: auto; }
  .scrollcol { min-height: 0; }
  .kv { grid-template-columns: 96px 1fr; }
}
@media print {
  .claim :deep(.rec), .actions { display: none; }
  .cols { grid-template-columns: 1fr; }
  .scrollcol { max-height: none; overflow: visible; }
}
</style>
