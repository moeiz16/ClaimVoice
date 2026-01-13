<script setup lang="ts">
// Photos from the text link, as a strip of tiles under the notice's Photos section. Before any arrive: dashed
// "Waiting for photos" tiles and, for staff who can work the claim, Resend link. A tile opens the photo in a dialog.
import type { Photo } from '~/types/api'
import { fmtTime } from '~/utils/format'

withDefaults(defineProps<{ photos: Photo[], linkSentAt?: string | null, canResend?: boolean }>(), { linkSentAt: null, canResend: false })
const emit = defineEmits<{ resend: [] }>()
const shown = ref<Photo | null>(null)
const open = computed({ get: () => !!shown.value, set: (v: boolean) => { if (!v) shown.value = null } })
</script>

<template>
  <div class="ph-wrap">
    <p class="k">
      <UIcon name="i-lucide-camera" class="size-4" />Photos<template v-if="photos.length">
        · {{ photos.length }} sent {{ fmtTime(photos[0]!.receivedAt) }} from the text link
      </template>
    </p>
    <div v-if="photos.length" class="photos">
      <button v-for="p in photos.slice(0, 6)" :key="p.id" type="button" class="ph" :aria-label="`Open photo${p.caption ? `: ${p.caption}` : ''}`" @click="shown = p">
        <img :src="p.thumbnailUrl" :alt="p.caption ?? 'Photo from the caller'" loading="lazy">
        <span v-if="p.caption">{{ p.caption }}</span>
      </button>
    </div>
    <div v-else class="photos">
      <div v-for="n in 3" :key="n" class="ph waiting" aria-hidden="true">
        <UIcon name="i-lucide-camera" class="size-6" />
      </div>
      <div class="wait">
        <p>
          Waiting for photos<template v-if="linkSentAt">
            · link sent {{ fmtTime(linkSentAt) }}
          </template>
        </p>
        <UButton v-if="canResend" size="sm" color="neutral" variant="soft" icon="i-lucide-send" @click="emit('resend')">
          Resend link
        </UButton>
      </div>
    </div>

    <UModal v-model:open="open" :title="shown?.caption ?? 'Photo from the caller'" :description="shown ? `Received ${fmtTime(shown.receivedAt)} · location details removed on upload` : undefined" :ui="{ content: 'sm:max-w-3xl' }">
      <template #body>
        <img v-if="shown" :src="shown.url" :alt="shown.caption ?? 'Photo from the caller'" class="big">
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.ph-wrap { border: 1px solid var(--cv-rule); border-radius: 6px; padding: 10px 12px 12px; background: var(--cv-surface); margin-top: 8px; }
.k { margin: 0 0 8px; display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 650; color: var(--cv-muted); }
.photos { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
.ph { aspect-ratio: 4 / 3; border-radius: 6px; position: relative; overflow: hidden; border: 0; padding: 0; background: var(--cv-sunk-2); display: block; cursor: zoom-in; }
.ph img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ph span { position: absolute; left: 8px; bottom: 6px; right: 8px; color: #fff; font-size: 11.5px; font-weight: 700; text-shadow: 0 1px 3px rgba(0, 0, 0, .6); text-align: left; }
.ph.waiting { background: transparent; border: 1.5px dashed var(--cv-faint); display: grid; place-items: center; color: var(--cv-muted); cursor: default; }
.wait { grid-column: span 3; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; gap: 8px; }
.wait p { margin: 0; font-size: 13.5px; color: var(--cv-muted); font-weight: 600; }
.big { width: 100%; border-radius: 6px; display: block; }
@media (max-width: 1100px) { .photos { grid-template-columns: repeat(3, minmax(0, 1fr)); } .wait { grid-column: 1 / -1; } }
@media print { .wait :deep(button) { display: none; } }
</style>
