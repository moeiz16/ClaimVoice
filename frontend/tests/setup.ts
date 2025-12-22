// Nuxt auto-imports Vue's APIs into components; outside a Nuxt build we provide the ones our components use.
import * as vue from 'vue'

const g = globalThis as Record<string, unknown>
for (const k of ['ref', 'computed', 'watch', 'watchEffect', 'reactive', 'onMounted', 'onBeforeUnmount', 'nextTick', 'toRaw', 'shallowRef', 'useId']) g[k] = (vue as Record<string, unknown>)[k]
g.useReducedMotionPref = () => vue.ref(false)
