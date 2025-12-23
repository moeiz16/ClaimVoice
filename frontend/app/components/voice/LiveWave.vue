<script setup lang="ts">
// A live conversation waveform: bars scroll right to left, ClaimVoice above the line, the caller below.
import type { LevelSource } from '~/composables/useLiveLevels'
import { dockColors, drawLive, themeColors } from '~/utils/waveform'

const props = withDefaults(defineProps<{
  seedKey: string
  source?: LevelSource
  palette?: 'theme' | 'dock'
  bar?: number
  gap?: number
  label?: string | null
}>(), { source: () => ({}), palette: 'theme', bar: 3, gap: 2, label: null })

const canvas = ref<HTMLCanvasElement | null>(null)
const seed = computed(() => props.seedKey)
const { buffer, version, current } = useLiveLevels(canvas, seed, props.source, 360)
const prefs = usePrefs()

function draw() {
  if (!canvas.value) return
  drawLive(canvas.value, buffer.bars, { bar: props.bar, gap: props.gap, colors: props.palette === 'dock' ? dockColors() : themeColors() })
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
