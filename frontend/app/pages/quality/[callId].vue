<script setup lang="ts">
// One call's quality review on its own page. Done → the next call in the same queue (the filters travel in the URL:
// ?status=, ?item=); when the queue is empty, back to the queue.
import { api } from '~/utils/api'

const route = useRoute()
const id = computed(() => String(route.params.callId))
useHead({ title: 'Quality review · ClaimVoice' })

async function next() {
  const status = String(route.query.status ?? 'needs_review')
  const item = typeof route.query.item === 'string' && route.query.item ? route.query.item : undefined
  try {
    const page = await api.qa.queue({ status, item, pageSize: 50 })
    const i = page.items.findIndex(x => x.callId === id.value)
    const n = (i >= 0 ? page.items[i + 1] : page.items[0]) ?? page.items.find(x => x.callId !== id.value)
    if (n && n.callId !== id.value) return navigateTo({ path: `/quality/${n.callId}`, query: route.query })
  }
  catch { /* the queue opens instead */ }
  return navigateTo({ path: '/quality', query: route.query })
}
</script>

<template>
  <ReviewPanel :key="id" :call-id="id" @done="next" />
</template>
