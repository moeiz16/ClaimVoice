<script setup lang="ts">
// The conversation as speech bubbles (DESIGN.md §3): ClaimVoice (and a person from Larkspur) on the left, the caller
// on the right, whispers as dashed blue notes ClaimVoice alone hears, system lines centred. Heard words are marked
// and link to their answers; removed card digits are a hatched pebble; sound tags are italic. Times are minutes into
// the call; when `seekable`, a time plays the recording from there. Interim words settle as the caller speaks.
import type { Turn } from '~/types/api'
import type { Mark } from '~/utils/transcript'
import { firstName, fmtClock, initials } from '~/utils/format'

const props = withDefaults(defineProps<{
  turns: Turn[]
  marks?: Record<string, Mark[]>
  callerLabel?: string
  showEn?: boolean
  currentId?: string | null
  signIds?: string[]
  seekable?: boolean
  interim?: string | null
  interimAt?: string | null
  lang?: string
  big?: boolean
  label?: string
}>(), { marks: () => ({}), callerLabel: 'The caller', showEn: true, currentId: null, signIds: () => [], seekable: false, interim: null, interimAt: null, lang: undefined, big: false, label: 'The conversation' })

const emit = defineEmits<{ span: [turnId: string, key: string], seek: [seconds: number] }>()
const callerFirst = computed(() => firstName(props.callerLabel))
const signs = computed(() => new Set(props.signIds))

function who(t: Turn): string {
  if (t.speaker === 'whisper') {
    const by = t.speakerLabel.split('·')[1]?.trim()
    return `Whisper, ClaimVoice only${by ? ` · ${by}` : ''}`
  }
  if (t.speaker === 'caller') return /^(caller|appelant)$/i.test(t.speakerLabel) ? callerFirst.value : firstName(t.speakerLabel)
  return t.speakerLabel
}
const side = (t: Turn) => (t.speaker === 'caller' ? 'right' : t.speaker === 'system' ? 'mid' : 'left')
</script>

<template>
  <ol class="conv" :class="{ big }" :aria-label="label">
    <slot name="before" />
    <li
      v-for="t in turns" :key="t.id" class="turn" :data-turn="t.id"
      :class="[t.speaker, side(t), { on: t.id === currentId, sign: signs.has(t.id), interrupted: t.interrupted }]"
      :aria-current="t.id === currentId ? 'true' : undefined"
    >
      <template v-if="t.speaker === 'system'">
        <p class="sys">
          {{ t.text }}
        </p>
      </template>
      <template v-else>
        <span class="av" aria-hidden="true">
          <CvMark v-if="t.speaker === 'line'" :size="26" />
          <UIcon v-else-if="t.speaker === 'whisper'" name="i-lucide-message-circle-more" class="size-4" />
          <template v-else>{{ initials(t.speaker === 'caller' ? (callerLabel || t.speakerLabel) : t.speakerLabel) }}</template>
        </span>
        <div class="b">
          <div class="meta">
            <b>{{ who(t) }}</b>
            <button v-if="seekable" type="button" class="tm num" :aria-label="`Play from ${fmtClock(t.atMs / 1000)}`" @click="emit('seek', t.atMs / 1000)">
              <UIcon name="i-lucide-play" class="size-3" />{{ fmtClock(t.atMs / 1000) }}
            </button>
            <time v-else class="tm num">{{ fmtClock(t.atMs / 1000) }}</time>
          </div>
          <p class="words" :lang="t.language === 'fr' ? 'fr' : undefined">
            <TranscriptText :text="t.text" :turn-id="t.id" :marks="marks[t.id]" @span="k => emit('span', t.id, k)" />
          </p>
          <span v-if="t.textEn && showEn" class="en">{{ t.textEn }}</span>
          <span v-if="signs.has(t.id)" class="signtag"><UIcon name="i-lucide-search" class="size-3.5" />A sign worth a closer look</span>
        </div>
      </template>
    </li>
    <li v-if="interim" class="turn caller right interim-turn" aria-hidden="true">
      <span class="av">{{ initials(callerLabel) }}</span>
      <div class="b">
        <div class="meta">
          <b>{{ callerFirst }}</b><span class="hearing">hearing now</span><time v-if="interimAt" class="tm num">{{ interimAt }}</time>
        </div>
        <p class="words" :lang="lang">
          <span v-for="(w, i) in interim.split(/\s+/)" :key="`${i}-${w}`" class="interim settle">{{ `${w} ` }}</span>
        </p>
      </div>
    </li>
    <slot name="after" />
  </ol>
</template>

<style scoped>
.conv { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }
.turn { display: flex; align-items: flex-end; gap: 10px; max-width: min(78%, 720px); animation: inflate-l var(--m-inflate) var(--ease-tide) both; }
.left { justify-self: start; transform-origin: 0 100%; }
.right { justify-self: end; flex-direction: row-reverse; transform-origin: 100% 100%; }
.mid { justify-self: center; max-width: 90%; }
.av {
  width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-family: var(--font-round); font-weight: 900; font-size: 12.5px; background: var(--cv-sand); color: var(--cv-caller);
}
.line .av { background: none; }
.person .av { background: var(--cv-person-wash); color: var(--cv-person); }
.whisper .av { background: var(--cv-person-wash); color: var(--cv-person); }
.b { padding: 10px 16px 12px; border-radius: 22px 22px 22px 6px; background: var(--cv-jade-wash); min-width: 0; transition: box-shadow 200ms; }
.right .b { border-radius: 22px 22px 6px 22px; background: var(--cv-surface); box-shadow: inset 0 0 0 2px var(--cv-sand-2); }
.person .b { background: var(--cv-person-wash); }
.whisper .b { background: transparent; box-shadow: inset 0 0 0 2px var(--cv-person); border-style: dashed; }
.meta { display: flex; align-items: baseline; gap: 8px; margin-bottom: 2px; }
.meta b { font-size: 12.5px; font-weight: 600; color: var(--cv-jade-ink); }
.right .meta { flex-direction: row-reverse; }
.right .meta b { color: var(--cv-caller); }
.person .meta b, .whisper .meta b { color: var(--cv-person); }
.tm { border: 0; background: none; padding: 0; display: inline-flex; align-items: center; gap: 3px; color: var(--cv-muted); font-size: 12px; font-weight: 500; }
button.tm:hover { color: var(--cv-jade-ink); text-decoration: underline; }
.words { margin: 0; font-size: calc(15.5px * var(--cv-caption-scale)); line-height: 1.5; }
.big .words { font-size: calc(19px * var(--cv-caption-scale)); line-height: 1.42; }
.whisper .words { color: var(--cv-person); font-weight: 500; }
.interrupted .words::after { content: " …"; color: var(--cv-faint); }
.en { display: block; margin-top: 4px; color: var(--cv-muted); font-size: 13.5px; }
.sys { margin: 0; padding: 6px 14px; border-radius: 999px; background: var(--cv-sunk); color: var(--cv-muted); font-size: 13px; text-align: center; }
.on .b { box-shadow: 0 0 0 3px var(--cv-jade); }
.right.on .b { box-shadow: inset 0 0 0 2px var(--cv-sand-2), 0 0 0 3px var(--cv-jade); }
.sign .b { box-shadow: inset 0 0 0 2px var(--cv-siu); }
.signtag { display: inline-flex; align-items: center; gap: 5px; margin-top: 6px; padding: 2px 10px; border-radius: 999px; background: var(--cv-siu-wash); color: var(--cv-siu); font-size: 12.5px; font-weight: 600; }
.hearing { font-size: 11.5px; font-weight: 600; color: var(--cv-jade-ink); }
@media (max-width: 720px) {
  .turn { max-width: 94%; }
  .av { width: 28px; height: 28px; font-size: 11px; }
  .big .words { font-size: calc(17px * var(--cv-caption-scale)); }
}
</style>
