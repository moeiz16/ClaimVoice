<script setup lang="ts">
// The tape (DESIGN.md §0.2): a call laid across the full width of the work area. The two-voice waveform runs along
// the middle; what Larkspur's side is saying right now is written above the line, what the caller is saying below it.
// The left column holds the line key or the play button and the talkback keys; the foot holds an input (whisper,
// say, typed call). Used by the live call, the claim file, quality review, the demo line and the landing.
withDefaults(defineProps<{ label?: string, dense?: boolean }>(), { label: 'The call', dense: false })
</script>

<template>
  <section class="tape" :class="{ dense }" :aria-label="label">
    <div v-if="$slots.key" class="key">
      <slot name="key" />
    </div>
    <div class="deck">
      <div v-if="$slots.above" class="above">
        <slot name="above" />
      </div>
      <div class="line">
        <slot />
      </div>
      <div v-if="$slots.pins" class="pins">
        <slot name="pins" />
      </div>
      <div v-if="$slots.below" class="below">
        <slot name="below" />
      </div>
    </div>
    <div v-if="$slots.foot" class="foot">
      <slot name="foot" />
    </div>
  </section>
</template>

<style scoped>
.tape {
  display: grid; grid-template-columns: 188px minmax(0, 1fr); gap: 0 24px; padding: 18px 32px 16px;
  background: var(--cv-sunk); border-bottom: 1px solid var(--cv-rule); position: relative;
}
.tape:not(:has(.key)) { grid-template-columns: minmax(0, 1fr); }
.key { display: flex; flex-direction: column; gap: 8px; align-self: center; }
.deck { min-width: 0; display: grid; gap: 6px; }
.above, .below {
  font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-weight: 600; letter-spacing: -0.01em;
  font-size: calc(26px * var(--cv-caption-scale)); line-height: 1.22; min-height: 1.22em;
}
.above { color: var(--cv-ink); }
.below { color: var(--cv-caller); text-align: right; }
.line { height: 92px; position: relative; }
.pins { position: relative; min-height: 26px; }
.foot { grid-column: 1 / -1; margin-top: 12px; }
.dense .above, .dense .below { font-size: calc(19px * var(--cv-caption-scale)); }
.dense .line { height: 70px; }
@media (max-width: 1100px) {
  .tape { grid-template-columns: minmax(0, 1fr); }
  .key { flex-direction: row; flex-wrap: wrap; align-self: start; margin-bottom: 10px; }
}
@media (max-width: 720px) {
  .tape { padding: 14px 16px 12px; }
  .above, .below { font-size: calc(19px * var(--cv-caption-scale)); }
  .line { height: 64px; }
}
</style>
