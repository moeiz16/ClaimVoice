<script setup lang="ts">
// Empty, info and error states on Nuxt UI's Alert: an icon and plain words, never colour alone. Errors are alerts
// (role="alert"); empty and info states are polite status notes.
withDefaults(defineProps<{ kind?: 'empty' | 'error' | 'info', title: string, body?: string | null, retry?: boolean }>(), { kind: 'empty', body: null, retry: false })
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="state-note">
  <UAlert
    :role="kind === 'error' ? 'alert' : 'status'"
    :color="kind === 'error' ? 'error' : kind === 'info' ? 'warning' : 'neutral'" variant="soft"
    :icon="kind === 'error' ? 'i-lucide-triangle-alert' : kind === 'info' ? 'i-lucide-clock' : 'i-lucide-audio-lines'"
    :title="title" :description="body ?? undefined"
    :actions="retry ? [{ label: 'Try again', icon: 'i-lucide-refresh-cw', color: 'neutral', variant: 'outline', size: 'md', onClick: () => $emit('retry') }] : undefined"
  >
    <template v-if="$slots.default" #description>
      <span v-if="body">{{ body }}</span>
      <slot />
    </template>
  </UAlert>
  </div>
</template>
