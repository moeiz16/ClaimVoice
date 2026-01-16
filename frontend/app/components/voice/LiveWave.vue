<script setup lang="ts">
// The live level of a call (it carries sound, so it stays): bars scroll right to left, ClaimVoice above the line,
// the caller below. Shown on the live call, the demo line and in the Bell.
import type { LevelSource } from '~/composables/useLiveLevels'
import { drawLive, themeColors } from '~/utils/waveform'

const props = withDefaults(defineProps<{
  seedKey: string
  source?: LevelSource
  bar?: number
  gap?: number
  label?: string | null
}>(), { source: () => ({}), bar: 3, gap: 2, label: null })

const canvas = ref<HTMLCanvasElement | null>(null)
const seed = computed(() => props.seedKey)
const { buffer, version, current } = useLiveLevels(canvas, seed, props.source, 360)
const prefs = usePrefs()

function draw() {
  if (!canvas.value) return
  drawLive(canvas.value, buffer.bars, { bar: props.bar, gap: props.gap, colors: themeColors() })
}
watch(version, draw)
watch(() => prefs.theme.value, () => nextTick(draw))
onMounted(() => nextTick(draw))
useResizeObserver(canvas, draw)
defineExpose({ current })
</script>

<template>
  <canvas ref="canvas" class="live-wave" :role="label ? 'img' : undefined" :aria-label="label ?? undefined" :aria-hidden="label ? undefined : 'true'" />
</template>

<style scoped>
.live-wave { display: block; width: 100%; height: 100%; }
</style>
