<script setup lang="ts">
// The claim file filling in during a live call: white sections on a tinted panel, every value with its source.
// Hover or focus a value and its words light up; click it and the transcript scrolls to them.
import type { ClaimFile, Lang } from '~/types/api'
import { linkKey } from '~/composables/useHeardLinks'
import { sectionDone } from '~/utils/marks'
import { sectionIcon } from '~/utils/labels'

const props = withDefaults(defineProps<{ file: ClaimFile | null, reference?: string | null, language?: Lang, ended?: boolean }>(), { reference: null, language: 'en', ended: false })
const links = useHeardLinks()
const sections = computed(() => (props.file?.sections ?? []).filter(s => s.slots.length))
const pairable = new Set(['loss', 'safety', 'photos', 'coverage', 'next_steps'])
const isLinked = (span: { turnId: string, start: number, end: number } | null) => !!span && (links.active.value === linkKey(span) || links.flashKey.value === linkKey(span))
</script>

<template>
  <section class="file" aria-label="Claim file">
    <div class="bar">
      <h2>Claim file</h2>
      <span v-if="ended" class="tag fast"><CvIcon name="check" size="s" />Filed</span>
      <span v-else class="tag orchid"><span class="live-dot" aria-hidden="true" />Filling in</span>
      <span class="r num">{{ [reference ? `Draft ${reference}` : '', language === 'fr' ? 'kept in French' : ''].filter(Boolean).join(' · ') }}</span>
    </div>
    <slot name="top" />
    <div v-if="!file" class="skel" aria-busy="true">
      <div v-for="n in 4" :key="n" class="sect">
        <span class="skeleton" style="width: 30%; height: 14px" />
        <span class="skeleton" style="width: 70%; height: 30px" />
        <span class="skeleton" style="width: 50%; height: 30px" />
      </div>
    </div>
    <div v-else class="grid">
      <div v-for="sec in sections" :key="sec.key" class="sect" :class="{ half: pairable.has(sec.key) }">
        <h3>
          <CvIcon :name="sectionIcon(sec.key)" size="s" />{{ sec.label }}
          <span v-if="sectionDone(sec.slots)" class="ok"><CvIcon name="check" size="s" />{{ sec.key === 'policy' ? 'Verified' : 'Checked' }}</span>
        </h3>
        <div v-for="s in sec.slots" :key="s.key" class="field" :class="{ linked: isLinked(s.span) }">
          <span class="k">{{ s.label }}</span>
          <div class="vals">
            <HeardValue
              :field="s" :linked="isLinked(s.span)" :lang="language === 'fr' ? 'fr' : undefined"
              @hover="on => links.hover(on ? s.span : null)" @activate="links.flash(s.span)"
            />
          </div>
        </div>
      </div>
      <div v-if="language === 'fr'" class="sect">
        <h3><CvIcon name="lang" size="s" />Language</h3>
        <div class="field">
          <span class="k">Service in</span>
          <div class="vals">
            <span class="src">French, chosen by the caller <small>Law 25: kept in French, English shown for staff</small></span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.file { background: var(--cv-sunk); border-radius: 28px; padding: 14px; overflow: auto; display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.bar { display: flex; align-items: center; gap: 10px; padding: 0 6px; flex-wrap: wrap; }
.bar h2 { font-size: 19px; font-weight: 700; }
.bar .r { margin-left: auto; font-size: 13px; color: var(--cv-muted); font-weight: 650; }
.bar .live-dot { background: var(--cv-orchid); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.sect { background: var(--cv-surface); border-radius: 20px; padding: 12px 14px; grid-column: 1 / -1; display: grid; gap: 2px; align-content: start; }
.sect.half { grid-column: auto; }
.skel .sect { gap: 10px; margin-bottom: 10px; }
h3 { font-family: var(--font-sans); font-size: 12.5px; font-weight: 750; color: var(--cv-muted); letter-spacing: 0; display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
h3 .ok { margin-left: auto; color: var(--cv-fast); display: inline-flex; gap: 4px; align-items: center; }
.field { display: grid; grid-template-columns: 116px 1fr; align-items: center; gap: 8px; padding: 3px 0; }
.half .field { grid-template-columns: 1fr; gap: 3px; padding: 4px 0; }
.k { font-size: 13px; color: var(--cv-muted); font-weight: 550; }
.vals { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.vals :deep(.heard) { min-height: 30px; font-size: 13.5px; padding: 3px 5px 3px 11px; }
.vals :deep(.heard .at) { height: 22px; font-size: 11.5px; }
.src { font-size: 13.5px; font-weight: 600; } .src small { color: var(--cv-muted); font-weight: 550; font-size: 12px; margin-left: 4px; }
@media (max-width: 720px) {
  .grid { grid-template-columns: 1fr; }
  .sect.half { grid-column: 1 / -1; }
  .field { grid-template-columns: 96px 1fr; }
  .half .field { grid-template-columns: 96px 1fr; }
}
</style>
