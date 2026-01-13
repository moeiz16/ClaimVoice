<script setup lang="ts">
// Sign in: "Pick up your lines." A top line with the mark, the slate-style heading, email and password, then the
// demo roles as numbered line keys for the sample organisation: picking a key signs in as that role. A quiet
// conversation breathes along the bottom edge.
import type { Role } from '~/types/api'
import { ApiError } from '~/utils/http'
import { ROLE_OPTIONS } from '~/utils/labels'

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
  ? { h: 'Prenez vos lignes.', l: 'Connectez-vous aux lignes de réclamations de Larkspur Mutual.', email: 'Courriel professionnel', pw: 'Mot de passe', go: 'Se connecter', forgot: 'Oublié?', demo: 'Démo : prenez une ligne', demoSub: 'Données d\'exemple. Tempête de vent chinook à Calgary, jeudi 8 janvier.', bad: 'Ce courriel et ce mot de passe ne correspondent pas. Réessayez ou demandez à votre administrateur.' }
  : { h: 'Pick up your lines.', l: 'Sign in to Larkspur Mutual\'s claims lines.', email: 'Work email', pw: 'Password', go: 'Sign in', forgot: 'Forgot it?', demo: 'Demo: pick up a line', demoSub: 'Sample data. Calgary Chinook windstorm, Thursday 8 January.', bad: 'That email and password don\'t match. Try again or ask your admin.' })
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

const quiet = { who: (t: number) => ((t % 9) < 3 ? 'cv' as const : (t % 9) < 6.5 ? 'caller' as const : 'gap' as const) }
</script>

<template>
  <div class="signin">
    <header class="top">
      <CvLogo />
      <UTabs v-model="lang" :items="langs" :content="false" variant="pill" size="sm" color="neutral" aria-label="Language / Langue" />
    </header>

    <main class="work">
      <div class="slate">
        <h1>{{ T.h }}</h1>
        <p class="l">
          {{ T.l }}
        </p>
      </div>

      <form class="form" novalidate @submit.prevent="submit">
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

      <section class="demo" aria-labelledby="demo-h">
        <h2 id="demo-h">
          {{ T.demo }}
        </h2>
        <p class="sub">
          {{ T.demoSub }}
        </p>
        <ol class="keys">
          <li v-for="(r, i) in ROLE_OPTIONS" :key="r.role">
            <button
              type="button" class="linekey" :data-demo-role="r.role" :disabled="!!busy" :aria-busy="busy === r.role"
              :aria-label="`Line ${i + 1}: sign in as ${r.person}, ${r.label.toLowerCase()}`" @click="demo(r.role)"
            >
              <span class="key" aria-hidden="true">
                <span class="n num">{{ i + 1 }}</span>
                <span class="lamp"><UIcon :name="busy === r.role ? 'i-lucide-loader-circle' : 'i-lucide-phone'" class="size-3" :class="{ 'animate-spin': busy === r.role }" /></span>
              </span>
              <span class="who">
                <b>{{ r.person }}</b>
                <span>{{ r.label }}</span>
                <small>{{ r.blurb }}</small>
              </span>
            </button>
          </li>
        </ol>
      </section>
    </main>

    <div class="quiet" aria-hidden="true">
      <LiveWave seed-key="sign-in-quiet" :source="quiet" :bar="3" :gap="3" />
    </div>
  </div>
</template>

<style scoped>
.signin { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr 120px; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 32px; border-bottom: 1px solid var(--cv-rule); }
.work { display: grid; align-content: start; }
.slate { padding: 32px 32px 18px; }
h1 { font-size: 44px; font-weight: 740; letter-spacing: -0.03em; line-height: 1.04; }
.l { color: var(--cv-muted); margin: 8px 0 0; font-size: 16px; }
.form { display: grid; gap: 16px; max-width: 460px; padding: 0 32px 28px; border-bottom: 1px solid var(--cv-rule); box-sizing: content-box; }
.err { display: flex; gap: 8px; align-items: flex-start; color: var(--cv-urgent); font-weight: 600; font-size: 14px; }
.err :deep(svg), .err > span:first-child { margin-top: 2px; }
.row { display: flex; align-items: center; gap: 18px; margin-top: 4px; }
.forgot { font-weight: 600; color: var(--cv-orchid-ink); }
.demo { padding: 22px 32px 28px; }
.demo h2 { font-size: 21px; font-weight: 700; }
.sub { margin: 4px 0 14px; color: var(--cv-muted); font-size: 14px; }
.keys { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 0 24px; max-width: 1120px; }
.keys li { border-top: 1px solid var(--cv-rule); }
.linekey { width: 100%; display: flex; gap: 14px; align-items: center; padding: 12px 6px 12px 0; border: 0; background: none; text-align: left; color: var(--cv-ink); border-radius: 6px; }
.linekey:hover:not(:disabled) .key { background: var(--cv-dock-raise); }
.linekey:hover:not(:disabled) b { text-decoration: underline; text-underline-offset: 4px; }
.linekey:disabled { opacity: .6; }
.key { flex: none; width: 52px; height: 50px; border-radius: 6px; display: grid; place-items: center; align-content: center; gap: 2px; background: var(--cv-dock); color: var(--cv-on-dock); box-shadow: inset 0 -2px 0 rgba(0, 0, 0, .3); transition: background 120ms; }
.key .n { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 19px; font-weight: 720; line-height: 1; }
.lamp { width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; background: color-mix(in srgb, var(--cv-dock-orchid) 30%, transparent); color: var(--cv-dock-orchid); }
.linekey[aria-busy="true"] .lamp { background: var(--cv-dock-orchid); color: #2A1530; }
.who { display: grid; min-width: 0; }
.who b { font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 16.5px; font-weight: 680; line-height: 1.2; }
.who span { font-size: 13.5px; font-weight: 600; color: var(--cv-muted); }
.who small { font-size: 12.5px; color: var(--cv-muted); }
.quiet { height: 120px; opacity: .5; }
@media (max-width: 720px) {
  .top { padding: 12px 16px; }
  .slate { padding: 22px 16px 14px; }
  h1 { font-size: 36px; }
  .form { padding: 0 16px 22px; max-width: none; box-sizing: border-box; }
  .demo { padding: 18px 16px 22px; }
  .signin { grid-template-rows: auto 1fr 90px; }
  .quiet { height: 90px; }
}
</style>
