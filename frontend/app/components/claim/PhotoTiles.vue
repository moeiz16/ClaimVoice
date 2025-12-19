<script setup lang="ts">
// Photos from the text link. Before any arrive: dashed "Waiting for photos" tiles.
import type { Photo } from '~/types/api'
import { fmtTime } from '~/utils/format'

defineProps<{ photos: Photo[], linkSentAt?: string | null }>()
const open = ref<Photo | null>(null)
</script>

<template>
  <div class="ph-wrap">
    <div class="group-label">
      <CvIcon name="camera" size="s" />Photos<template v-if="photos.length">
        · sent {{ fmtTime(photos[0]!.receivedAt) }} from the text link
      </template>
    </div>
    <div v-if="photos.length" class="photos">
      <button v-for="p in photos.slice(0, 6)" :key="p.id" type="button" class="ph" :aria-label="`Open photo${p.caption ? `: ${p.caption}` : ''}`" @click="open = p">
        <img :src="p.thumbnailUrl" :alt="p.caption ?? 'Photo from the caller'" loading="lazy">
        <span v-if="p.caption">{{ p.caption }}</span>
      </button>
    </div>
    <div v-else class="photos">
      <div v-for="n in 3" :key="n" class="ph waiting">
        <CvIcon name="camera" />
      </div>
      <p class="wait">
        Waiting for photos<template v-if="linkSentAt">
          · link sent {{ fmtTime(linkSentAt) }}
        </template>
      </p>
    </div>
    <CvSheet :open="!!open" :title="open?.caption ?? 'Photo from the caller'" wide @close="open = null">
      <img v-if="open" :src="open.url" :alt="open.caption ?? 'Photo from the caller'" class="big">
      <p v-if="open" class="meta">
        Received {{ fmtTime(open.receivedAt) }} · location details removed on upload
      </p>
    </CvSheet>
  </div>
</template>

<style scoped>
.ph-wrap { margin-top: 16px; }
.photos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
.ph { aspect-ratio: 4 / 3; border-radius: 14px; position: relative; overflow: hidden; border: 0; padding: 0; background: var(--cv-sunk-2); display: block; }
.ph img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ph span { position: absolute; left: 8px; bottom: 6px; right: 8px; color: #fff; font-size: 11.5px; font-weight: 700; text-shadow: 0 1px 3px rgba(0, 0, 0, .6); text-align: left; }
.ph.waiting { background: transparent; border: 1.5px dashed var(--cv-faint); display: grid; place-items: center; color: var(--cv-faint); }
.wait { grid-column: 1 / -1; margin: 0; font-size: 13px; color: var(--cv-muted); }
.big { width: 100%; border-radius: 20px; display: block; }
.meta { color: var(--cv-muted); font-size: 13px; }
</style>
