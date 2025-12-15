<script setup lang="ts">
// Empty and error states. Errors are a red ribbon with an icon and plain words, never colour alone.
withDefaults(defineProps<{ kind?: 'empty' | 'error' | 'info', title: string, body?: string | null, retry?: boolean }>(), { kind: 'empty', body: null, retry: false })
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="note" :class="kind" :role="kind === 'error' ? 'alert' : 'status'">
    <span class="ic"><CvIcon :name="kind === 'error' ? 'urgent' : kind === 'info' ? 'clock' : 'waves'" /></span>
    <div>
      <b>{{ title }}</b>
      <p v-if="body">
        {{ body }}
      </p>
      <slot />
    </div>
    <button v-if="retry" class="btn sm soft on-sunk" type="button" @click="$emit('retry')">
      <CvIcon name="refresh" size="s" />Try again
    </button>
  </div>
</template>

<style scoped>
.note { display: flex; align-items: center; gap: 14px; padding: 12px 14px 12px 12px; border-radius: 28px; background: var(--cv-sunk); }
.note.error { background: var(--cv-urgent-wash); color: var(--cv-ink); }
.note.error .ic { color: var(--cv-urgent); }
.note.info { background: var(--cv-siu-wash); }
.note.info .ic { color: var(--cv-siu); }
.ic { width: 42px; height: 42px; border-radius: 50%; background: var(--cv-surface); display: grid; place-items: center; color: var(--cv-orchid-ink); flex: none; }
b { font-family: var(--font-display); font-size: 18px; font-weight: 700; letter-spacing: -0.02em; display: block; }
p { margin: 2px 0 0; color: var(--cv-muted); font-size: 14px; }
.btn { margin-left: auto; }
</style>
