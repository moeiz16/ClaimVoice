<script setup lang="ts">
// Transcript text as segments: plain words, heard spans (linked to claim-file fields), closer-look phrases (amber),
// sound tags in italics, and removed card digits as the hatched "■■■■ removed" pill. Plain text only, never HTML.
import { linkKey } from '~/composables/useHeardLinks'
import { segmentText, type Mark } from '~/utils/transcript'

const props = withDefaults(defineProps<{ text: string, turnId: string, marks?: Mark[] }>(), { marks: () => [] })
const emit = defineEmits<{ span: [key: string] }>()
const links = useHeardLinks()
const segs = computed(() => segmentText(props.text, props.marks))
const markOf = (key: string) => props.marks.find(m => m.key === key)
function spanKey(key: string) {
  const m = markOf(key)
  return m ? linkKey({ turnId: props.turnId, start: m.start, end: m.end }) : null
}
function hover(key: string, on: boolean) {
  const m = markOf(key)
  links.hover(on && m ? { turnId: props.turnId, start: m.start, end: m.end } : null)
}
</script>

<template>
  <template v-for="(s, i) in segs" :key="i">
    <template v-if="s.type === 'text'">
      {{ s.text }}
    </template>
    <span v-else-if="s.type === 'sound'" class="sound">{{ s.text }}</span>
    <span v-else-if="s.type === 'hush'" class="hush" role="img" aria-label="Card number removed">■■■■ removed</span>
    <mark
      v-else-if="s.type === 'span'" class="span" :class="{ sign: s.kind === 'sign', linked: links.active.value === spanKey(s.key), lit: links.flashKey.value === spanKey(s.key) }"
      :data-span="spanKey(s.key)" tabindex="0" @mouseenter="hover(s.key, true)" @mouseleave="hover(s.key, false)" @focus="hover(s.key, true)" @blur="hover(s.key, false)"
      @click="emit('span', s.key)" @keydown.enter="emit('span', s.key)"
    >{{ s.text }}</mark>
  </template>
</template>
