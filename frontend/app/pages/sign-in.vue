<script setup lang="ts">
// Sign in (DESIGN.md §3): "Who's picking up today?" The demo people of the sample organisation as round faces (a
// profile picker: choosing a face signs in as that role), then the work email and password in a rounded card.
import type { Role } from '~/types/api'
import { ApiError } from '~/utils/http'
import { ROLE_OPTIONS } from '~/utils/labels'
import { initials } from '~/utils/format'

definePageMeta({ layout: 'public' })
useHead({ title: 'Sign in · ClaimVoice' })

const prefs = usePrefs()
const fr = computed(() => prefs.lang.value === 'fr')
const session = useSession()
const route = useRoute()
const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const busy = ref<string | null>(null)

const T = computed(() => fr.value
  ? { h: 'Qui répond aujourd\'hui ?', l: 'Choisissez une personne de Larkspur Mutual pour essayer la démo, ou connectez-vous avec votre courriel.', email: 'Courriel professionnel', pw: 'Mot de passe', go: 'Se connecter', forgot: 'Oublié?', form: 'Ou connectez-vous avec votre courriel', demoSub: 'Données d\'exemple. Tempête de vent chinook à Calgary, jeudi 8 janvier.', bad: 'Ce courriel et ce mot de passe ne correspondent pas. Réessayez ou demandez à votre administrateur.' }
  : { h: 'Who\'s picking up today?', l: 'Choose someone at Larkspur Mutual to try the demo, or sign in with your work email.', email: 'Work email', pw: 'Password', go: 'Sign in', forgot: 'Forgot it?', form: 'Or sign in with your work email', demoSub: 'Sample data. Calgary Chinook windstorm, Thursday 8 January.', bad: 'That email and password don\'t match. Try again or ask your admin.' })
const langs = [{ value: 'en', label: 'EN' }, { value: 'fr', label: 'FR' }]
const lang = computed({ get: () => prefs.lang.value, set: (v: string | number) => { prefs.lang.value = v === 'fr' ? 'fr' : 'en' } })

function next(): string {
  const n = route.query.next
  return typeof n === 'string' && n.startsWith('/') && !n.startsWith('//') ? n : ''
}

async function submit() {
  error.value = null
  busy.value = 'form'
  try {
    const me = await session.signIn(email.value.trim(), password.value)
    await navigateTo(next() || landingFor(me))
  }
  catch (e) {
    error.value = e instanceof ApiError && e.status === 429 ? 'Too many tries. Wait a few minutes, then try again.' : T.value.bad
  }
  busy.value = null
}

async function demo(role: Role) {
  error.value = null
  busy.value = role
  try {
    const me = await session.demo(role)
    await navigateTo(next() || landingFor(me))
  }
  catch {
    error.value = 'Demo sign-in isn\'t available here. Use your email and password.'
  }
  busy.value = null
}

const TONE = ['jade', 'person', 'siu', 'sand', 'jade', 'person'] as const
</script>

<template>
  <div class="signin">
    <header class="top">
      <CvLogo />
      <UTabs v-model="lang" :items="langs" :content="false" size="sm" color="neutral" aria-label="Language / Langue" />
    </header>

    <main class="work">
      <h1>{{ T.h }}</h1>
      <p class="l">
        {{ T.l }}
      </p>

      <section class="faces" aria-label="Demo sign-in">
        <ul>
          <li v-for="(r, i) in ROLE_OPTIONS" :key="r.role" :style="{ '--i': i }">
            <button
              type="button" class="face" :class="`t-${TONE[i]}`" :data-demo-role="r.role" :disabled="!!busy" :aria-busy="busy === r.role"
              :aria-label="`Sign in as ${r.person}, ${r.label.toLowerCase()}`" @click="demo(r.role)"
            >
              <span class="ring" aria-hidden="true">
                <span class="disc round">{{ initials(r.person) }}</span>
                <UIcon v-if="busy === r.role" name="i-lucide-loader-circle" class="spin animate-spin" />
              </span>
              <b class="round">{{ r.person.split(' ')[0] }}</b>
              <span class="role">{{ r.label }}</span>
              <small>{{ r.blurb }}</small>
            </button>
          </li>
        </ul>
        <p class="sub">
          <UIcon name="i-lucide-info" class="size-4" />{{ T.demoSub }}
        </p>
      </section>

      <form class="form" novalidate @submit.prevent="submit">
        <h2>{{ T.form }}</h2>
        <UFormField :label="T.email" name="email" :error="!!error">
          <UInput v-model="email" type="email" autocomplete="username" required size="xl" icon="i-lucide-mail" class="w-full" />
        </UFormField>
        <UFormField :label="T.pw" name="password" :error="!!error">
          <UInput v-model="password" type="password" autocomplete="current-password" required size="xl" icon="i-lucide-lock" class="w-full" />
          <template v-if="error" #error>
            <span id="signin-err" class="err" role="alert"><UIcon name="i-lucide-triangle-alert" class="size-4 shrink-0" />{{ error }}</span>
          </template>
        </UFormField>
        <div class="row">
          <UButton type="submit" size="xl" trailing-icon="i-lucide-arrow-right" :loading="busy === 'form'" :disabled="!!busy">
            {{ T.go }}
          </UButton>
          <ULink href="mailto:nadia.kassem@larkspurmutual.ca?subject=ClaimVoice%20password" external class="forgot">
            {{ T.forgot }}
          </ULink>
        </div>
      </form>
    </main>
  </div>
</template>

<style scoped>
.signin { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 40px; }
.work { display: grid; justify-items: center; align-content: start; text-align: center; padding: 28px 24px 64px; }
h1 { font-size: 72px; font-weight: 900; letter-spacing: -0.03em; line-height: .98; max-width: 14ch; }
.l { color: var(--cv-muted); margin: 14px 0 0; font-size: 17px; max-width: 52ch; }
.faces { margin-top: 40px; display: grid; justify-items: center; gap: 18px; width: 100%; }
.faces ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(6, minmax(0, 168px)); gap: 18px; justify-content: center; width: 100%; }
.faces li { animation: rise 420ms var(--ease-tide) both; animation-delay: calc(var(--i) * 50ms); }
.face { width: 100%; border: 0; background: none; padding: 6px 4px 10px; display: grid; justify-items: center; gap: 4px; color: var(--cv-ink); border-radius: 26px; }
.face:disabled { opacity: .6; }
.ring { position: relative; width: 124px; height: 124px; border-radius: 50%; display: grid; place-items: center; margin-bottom: 8px; box-shadow: inset 0 0 0 4px transparent; transition: box-shadow 180ms, transform 220ms var(--ease-spring); }
.disc { width: 108px; height: 108px; border-radius: 50%; display: grid; place-items: center; font-size: 38px; font-weight: 900; letter-spacing: -0.02em; box-shadow: inset 0 -5px 0 var(--cv-lip); }
.t-jade .disc { background: var(--cv-jade-wash); color: var(--cv-jade-ink); }
.t-person .disc { background: var(--cv-person-wash); color: var(--cv-person); }
.t-siu .disc { background: var(--cv-siu-wash); color: var(--cv-siu); }
.t-sand .disc { background: var(--cv-sand); color: var(--cv-caller); }
.face:hover:not(:disabled) .ring, .face:focus-visible .ring { box-shadow: inset 0 0 0 4px var(--cv-jade); transform: translateY(-3px); }
.face:focus-visible { outline: none; }
.spin { position: absolute; bottom: 2px; right: 6px; width: 26px; height: 26px; color: var(--cv-jade); }
.face b { font-size: 21px; font-weight: 900; }
.role { font-size: 13.5px; font-weight: 500; }
.face small { font-size: 12.5px; color: var(--cv-muted); line-height: 1.35; max-width: 18ch; }
.sub { margin: 0; display: inline-flex; gap: 6px; align-items: center; color: var(--cv-muted); font-size: 13.5px; }
.form { margin-top: 44px; display: grid; gap: 16px; width: min(460px, 100%); padding: 26px 28px 28px; border-radius: 32px; background: var(--cv-surface); box-shadow: var(--cv-shadow-soft); text-align: left; }
.form h2 { font-size: 22px; font-weight: 900; }
.err { display: flex; gap: 8px; align-items: flex-start; color: var(--cv-urgent); font-weight: 500; font-size: 14px; }
.err :deep(svg), .err > span:first-child { margin-top: 2px; }
.row { display: flex; align-items: center; gap: 18px; margin-top: 4px; }
.forgot { font-weight: 500; color: var(--cv-jade-ink); }
@media (max-width: 1100px) {
  .faces ul { grid-template-columns: repeat(3, minmax(0, 168px)); }
}
@media (max-width: 720px) {
  .top { padding: 14px 16px; }
  .work { padding: 12px 16px 48px; }
  h1 { font-size: 42px; }
  .l { font-size: 15.5px; }
  .faces { margin-top: 26px; }
  .faces ul { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .ring { width: 96px; height: 96px; }
  .disc { width: 84px; height: 84px; font-size: 30px; }
  .form { padding: 20px 18px 22px; border-radius: 26px; margin-top: 32px; }
}
</style>
