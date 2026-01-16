<script setup lang="ts">
// The top of every signed-in page (DESIGN.md §3). On a place's own page the heading is its question, and the heading
// is the navigation: pressing it drops the Questions sheet. On a record (a call, a claim, a review) a crumb pebble
// ("‹ Lines", with its own chevron) sits above the record's name instead. Under the heading: the answer, in one
// sentence, then any page controls, all left-aligned. The Bell sits at the top right, in the layout.
withDefaults(defineProps<{
  title: string
  caption?: string | null
  back?: { to: string, label: string } | null
  eyebrow?: string | null
  /** Smaller heading for long record names. */
  compact?: boolean
}>(), { caption: null, back: null, eyebrow: null, compact: false })

const sheet = useSheet()
</script>

<template>
  <header class="pagehead" :class="{ record: !!back, compact }">
    <div class="top">
      <NuxtLink v-if="!back" to="/" class="mk" aria-label="ClaimVoice home"><CvMark :size="40" /></NuxtLink>
      <div v-else class="crumb">
        <NuxtLink :to="back.to" class="cb-back"><UIcon name="i-lucide-arrow-left" class="size-4" />{{ back.label }}</NuxtLink>
        <button type="button" class="cb-more" aria-haspopup="dialog" :aria-expanded="sheet.open.value" aria-label="Open the other questions" @click="sheet.show()">
          <UIcon name="i-lucide-chevron-down" class="size-4" />
        </button>
      </div>
      <p v-if="eyebrow || $slots.eyebrow" class="eyebrow">
        <span v-if="eyebrow">{{ eyebrow }}</span>
        <slot name="eyebrow" />
      </p>
    </div>
    <h1 v-if="!back" class="q">
      <button type="button" class="qbtn" aria-haspopup="dialog" :aria-expanded="sheet.open.value" @click="sheet.show()">
        <span class="qt">{{ title }}</span>
        <span class="chev" aria-hidden="true"><UIcon name="i-lucide-chevron-down" /></span>
        <span class="sr-only-cv">Open the other questions</span>
      </button>
    </h1>
    <h1 v-else class="name">
      {{ title }}<slot name="title-after" />
    </h1>
    <p v-if="caption || $slots.caption" class="answer">
      <slot name="caption">{{ caption }}</slot>
    </p>
    <div v-if="$slots.default" class="ctl">
      <slot />
    </div>
  </header>
</template>

<style scoped>
.pagehead { padding: 28px 96px 26px 0; display: grid; gap: 10px; justify-items: start; }
.top { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; min-height: 44px; }
.mk { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 16px; margin-left: -4px; }
.eyebrow { margin: 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; color: var(--cv-muted); font-size: 14px; }

/* The question: Nunito Black, cushioned; the heading is a button that drops the Questions sheet. */
.q { font-size: 62px; line-height: .98; font-weight: 900; letter-spacing: -0.025em; margin-top: 6px; }
.qbtn {
  display: inline-flex; align-items: center; gap: 14px; border: 0; background: none; padding: 0; text-align: left;
  font: inherit; letter-spacing: inherit; color: inherit; border-radius: 18px; text-shadow: inherit;
}
.chev {
  flex: none; width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; align-self: center;
  background: var(--cv-jade-wash); color: var(--cv-jade-ink); font-size: 26px; text-shadow: none;
  box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--cv-jade) 25%, transparent);
  transition: background-color 160ms, color 160ms, transform 200ms var(--ease-spring);
}
.qbtn:hover .chev, .qbtn[aria-expanded="true"] .chev { background: var(--cv-jade); color: var(--cv-on-jade); }
.qbtn[aria-expanded="true"] .chev { transform: rotate(180deg); }
.qbtn:active .chev { transform: translateY(2px); }

/* A record's name, under the crumb. */
.name { font-size: 52px; line-height: 1; font-weight: 900; letter-spacing: -0.025em; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.compact .name { font-size: 42px; }
.crumb { display: inline-flex; align-items: center; border-radius: 999px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); }
.cb-back {
  display: inline-flex; align-items: center; gap: 7px; height: 40px; padding: 0 12px 0 14px; border-radius: 999px 0 0 999px;
  color: var(--cv-ink); text-decoration: none; font-weight: 500; font-size: 14px;
}
.cb-back:hover { background: var(--cv-sunk); }
.cb-more { width: 40px; height: 40px; border: 0; border-left: 2px solid var(--cv-sunk); border-radius: 0 999px 999px 0; background: none; display: grid; place-items: center; color: var(--cv-muted); }
.cb-more:hover { background: var(--cv-jade-wash); color: var(--cv-jade-ink); }

.answer { margin: 4px 0 0; font-size: 18px; line-height: 1.45; max-width: 64ch; color: var(--cv-ink); font-weight: 350; }
.answer :deep(b), .answer :deep(strong) { font-weight: 600; }
.ctl { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 8px; }

@media (max-width: 720px) {
  .pagehead { padding: 16px 64px 18px 0; gap: 8px; }
  .q { font-size: 38px; }
  .chev { width: 36px; height: 36px; font-size: 20px; align-self: flex-end; margin-bottom: 2px; }
  .qbtn { gap: 10px; }
  .name, .compact .name { font-size: 34px; }
  .answer { font-size: 16px; }
  .ctl :deep(.hide-phone) { display: none; }
}
</style>
