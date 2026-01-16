<script setup lang="ts">
// Settings (DESIGN.md §3): "How should the line behave?" On /settings the sections are an inset group of rows, as a
// phone's settings are, each with a line on what it decides; a section opens as its own page under a crumb. Changes
// take effect for calls answered after the change; a live call keeps the script it started with. Every change is
// written to the activity log.
import { questionFor } from '~/utils/places'

useHead({ title: 'Settings · ClaimVoice' })
const route = useRoute()
const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const groups = [
  {
    title: 'What ClaimVoice says',
    items: [
      { to: '/settings/scripts', label: 'Scripts', icon: 'i-lucide-message-circle-more', tone: 'jade', about: 'The questions it asks, in order, for each kind of claim' },
      { to: '/settings/languages', label: 'Languages', icon: 'i-lucide-languages', tone: 'jade', about: 'English and French: the first language, the voice and its pace' },
    ],
  },
  {
    title: 'When a person steps in',
    items: [
      { to: '/settings/handoff', label: 'Hand-off rules', icon: 'i-lucide-user-round-plus', tone: 'person', about: 'Urgent words, how long a caller waits, and when to offer a person' },
      { to: '/settings/people', label: 'People', icon: 'i-lucide-users-round', tone: 'person', about: 'Who can sign in, their role, and invitations' },
    ],
  },
  {
    title: 'What is kept, and for how long',
    items: [
      { to: '/settings/consent', label: 'Consent rules', icon: 'i-lucide-shield-check', tone: 'siu', about: 'Recording consent by state and province, in the words the caller hears' },
      { to: '/settings/retention', label: 'Retention', icon: 'i-lucide-clock', tone: 'siu', about: 'How long recordings, words and photos are kept' },
      { to: '/settings/privacy', label: 'Privacy', icon: 'i-lucide-lock', tone: 'siu', about: 'Requests to see or delete what we hold, and what is never kept' },
    ],
  },
]
const flat = groups.flatMap(g => g.items)
const current = computed(() => flat.find(i => route.path.startsWith(i.to)) ?? null)
const answer = computed(() => `Seven things decide it. Changes apply to calls answered after you save${manage.value ? '' : '; you can read them, and an administrator changes them'}.`)
</script>

<template>
  <div>
    <template v-if="!current">
      <PageHead :title="questionFor('settings')" :caption="answer">
        <UButton v-if="can('audit:read')" to="/activity" color="neutral" variant="soft" icon="i-lucide-link-2">
          Who changed what
        </UButton>
      </PageHead>
      <div class="groups">
        <section v-for="g in groups" :key="g.title" class="group" :aria-label="g.title">
          <h2 class="gh">
            {{ g.title }}
          </h2>
          <ul class="inset">
            <li v-for="i in g.items" :key="i.to">
              <NuxtLink :to="i.to" class="row">
                <span class="ic" :class="`t-${i.tone}`" aria-hidden="true"><UIcon :name="i.icon" /></span>
                <span class="tx"><b>{{ i.label }}</b><small>{{ i.about }}</small></span>
                <UIcon name="i-lucide-chevron-right" class="size-5 chev" />
              </NuxtLink>
            </li>
          </ul>
        </section>
      </div>
    </template>
    <template v-else>
      <PageHead :title="current.label" :caption="current.about + '.'" :back="{ to: '/settings', label: 'Settings' }" />
      <NuxtPage />
    </template>
  </div>
</template>

<style scoped>
.groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 24px; align-items: start; }
.gh { font-size: 15px; font-family: var(--font-sans); font-weight: 500; color: var(--cv-muted); letter-spacing: 0; margin: 0 0 8px 18px; }
.inset { list-style: none; margin: 0; padding: 0; display: grid; gap: 3px; border-radius: 26px; overflow: hidden; box-shadow: var(--cv-shadow-soft); }
.row { display: flex; align-items: center; gap: 14px; padding: 16px 18px; background: var(--cv-surface); color: inherit; text-decoration: none; min-height: 76px; }
.row:hover { background: var(--cv-jade-wash); }
.row:focus-visible { outline-offset: -3px; }
.ic { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; font-size: 21px; flex: none; }
.t-jade { background: var(--cv-jade); color: var(--cv-on-jade); }
.t-person { background: var(--cv-person); color: #fff; }
.t-siu { background: var(--cv-siu); color: #fff; }
[data-theme="dark"] .t-person, [data-theme="dark"] .t-siu { color: var(--cv-bg); }
.tx { display: grid; flex: 1; min-width: 0; }
.tx b { font-family: var(--font-round); font-weight: 850; font-size: 19px; letter-spacing: -0.01em; }
.tx small { color: var(--cv-muted); font-size: 13.5px; }
.chev { color: var(--cv-faint); flex: none; }
</style>
