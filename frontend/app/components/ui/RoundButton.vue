<script setup lang="ts">
// A round call button with its word underneath, as a phone's in-call screen has them (DESIGN.md §7). Pressed state
// is said by aria-pressed and the word, not by colour alone.
const props = withDefaults(defineProps<{
  icon: string
  label: string
  pressed?: boolean | null
  tone?: 'neutral' | 'jade' | 'person' | 'urgent'
  size?: 'md' | 'lg'
  disabled?: boolean
  to?: string | null
}>(), { pressed: null, tone: 'neutral', size: 'md', disabled: false, to: null })
defineEmits<{ click: [e: MouseEvent] }>()
const NuxtLink = resolveComponent('NuxtLink')
const tag = computed(() => (props.to ? NuxtLink : 'button'))
</script>

<template>
  <component
    :is="tag" :to="to ?? undefined" :type="to ? undefined : 'button'" class="rb" :class="[`t-${tone}`, `s-${size}`, { on: pressed }]"
    :aria-pressed="pressed === null ? undefined : pressed" :disabled="disabled || undefined" @click="(e: MouseEvent) => !disabled && $emit('click', e)"
  >
    <span class="c" aria-hidden="true"><UIcon :name="icon" /></span>
    <span class="w">{{ label }}</span>
  </component>
</template>

<style scoped>
.rb { display: inline-grid; justify-items: center; gap: 6px; border: 0; background: none; padding: 0; color: var(--cv-ink); text-decoration: none; border-radius: 18px; min-width: 64px; }
.c {
  width: 52px; height: 52px; border-radius: 50%; display: grid; place-items: center; font-size: 21px;
  background: var(--cv-sunk); color: var(--cv-ink); box-shadow: inset 0 -3px 0 var(--cv-lip);
  transition: transform 140ms var(--ease-spring), background-color 160ms, color 160ms;
}
.s-lg .c { width: 64px; height: 64px; font-size: 25px; }
.w { font-size: 12.5px; font-weight: 500; line-height: 1.2; text-align: center; max-width: 92px; }
.rb:hover .c { background: var(--cv-sunk-2); }
.rb:active .c { transform: translateY(2px); box-shadow: inset 0 -1px 0 var(--cv-lip); }
.rb:focus-visible { outline: none; }
.rb:focus-visible .c { outline: 3px solid var(--cv-jade); outline-offset: 3px; }
.t-jade .c, .on .c { background: var(--cv-jade); color: var(--cv-on-jade); }
.t-jade:hover .c, .on:hover .c { background: color-mix(in srgb, var(--cv-jade) 90%, black); }
.t-person .c { background: var(--cv-person); color: #fff; }
.t-urgent .c { background: var(--cv-urgent); color: #fff; }
[data-theme="dark"] .t-person .c, [data-theme="dark"] .t-urgent .c { color: var(--cv-bg); }
.rb[disabled] { opacity: .45; cursor: not-allowed; }
</style>
