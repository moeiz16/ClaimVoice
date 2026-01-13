/* eslint-disable vue/one-component-per-file, vue/require-default-prop -- test stand-ins for Nuxt UI components */
// Nuxt auto-imports Vue's APIs into components; outside a Nuxt build we provide the ones our components use, plus
// light stand-ins for the Nuxt UI components they render (enough to check structure, words and wiring).
import { config } from '@vue/test-utils'
import * as vue from 'vue'

const g = globalThis as Record<string, unknown>
for (const k of ['ref', 'computed', 'watch', 'watchEffect', 'reactive', 'onMounted', 'onBeforeUnmount', 'nextTick', 'toRaw', 'shallowRef', 'useId', 'resolveComponent']) g[k] = (vue as Record<string, unknown>)[k]
g.useReducedMotionPref = () => vue.ref(false)
const state = new Map<string, vue.Ref<unknown>>()
g.useState = (key: string, init?: () => unknown) => {
  if (!state.has(key)) state.set(key, vue.ref(init ? init() : null))
  return state.get(key)
}

const { defineComponent, h } = vue
const UIcon = defineComponent({ props: { name: { type: String, default: '' } }, setup: p => () => h('svg', { 'data-icon': p.name, 'aria-hidden': 'true' }) })
const UBadge = defineComponent({
  props: { color: String, variant: String, size: String, icon: String },
  setup: (p, { slots }) => () => h('span', { 'class': 'u-badge', 'data-color': p.color, 'data-variant': p.variant }, [p.icon ? h(UIcon, { name: p.icon }) : null, slots.default?.()]),
})
const UStepper = defineComponent({
  props: { items: { type: Array, default: () => [] }, modelValue: Number },
  setup: p => () => h('ol', { class: 'u-stepper' }, (p.items as { title: string }[]).map((it, i) => h('li', { 'data-active': i === p.modelValue ? 'true' : undefined }, it.title))),
})
const USkeleton = defineComponent({ setup: () => () => h('span', { class: 'u-skeleton' }) })
const passthrough = (tag: string) => defineComponent({ inheritAttrs: true, setup: (_p, { slots }) => () => h(tag, slots.default?.()) })

config.global.components = { UIcon, UBadge, UStepper, USkeleton, UTooltip: passthrough('span'), NuxtLink: defineComponent({ props: { to: String }, setup: (p, { slots }) => () => h('a', { href: p.to }, slots.default?.()) }) }
