<script setup lang="ts">
// Sign in: "Pick up your lines." Email and password, plus demo sign-in by role for the sample organisation. A quiet
// conversation plays along the bottom edge.
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
const showRoles = ref(false)

const T = computed(() => fr.value
  ? { h: ['Prenez', 'vos lignes.'], l: 'Connectez-vous aux lignes de réclamations de Larkspur Mutual.', email: 'Courriel professionnel', pw: 'Mot de passe', go: 'Se connecter', forgot: 'Oublié?', demo: 'Démo : Renée Kowalchuk, superviseure', demoSub: 'Données d\'exemple. Tempête de vent chinook à Calgary, jeudi 8 janvier.', other: 'Ou entrer avec un autre rôle', bad: 'Ce courriel et ce mot de passe ne correspondent pas. Réessayez ou demandez à votre administrateur.' }
  : { h: ['Pick up', 'your lines.'], l: 'Sign in to Larkspur Mutual\'s claims lines.', email: 'Work email', pw: 'Password', go: 'Sign in', forgot: 'Forgot it?', demo: 'Demo: Renée Kowalchuk, claims supervisor', demoSub: 'Sample data. Calgary Chinook windstorm, Thursday 8 January.', other: 'Or step in as another role', bad: 'That email and password don\'t match. Try again or ask your admin.' })

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
    <header><CvLogo /></header>
    <main>
      <form class="box" novalidate @submit.prevent="submit">
        <h1>{{ T.h[0] }}<br>{{ T.h[1] }}</h1>
        <p class="l">
          {{ T.l }}
        </p>
        <label for="e">{{ T.email }}</label>
        <input id="e" v-model="email" class="field-input" type="email" autocomplete="username" required :aria-invalid="!!error" aria-describedby="signin-err">
        <label for="p">{{ T.pw }}</label>
        <input id="p" v-model="password" class="field-input" type="password" autocomplete="current-password" required :aria-invalid="!!error" aria-describedby="signin-err">
        <p v-if="error" id="signin-err" class="err" role="alert">
          <CvIcon name="urgent" size="s" />{{ error }}
        </p>
        <div class="row">
          <button class="btn primary" type="submit" :disabled="!!busy">
            {{ T.go }}<CvIcon name="right" size="s" />
          </button>
          <a href="mailto:nadia.kassem@larkspurmutual.ca?subject=ClaimVoice%20password">{{ T.forgot }}</a>
          <span class="seg lang" role="group" aria-label="Language / Langue">
            <button type="button" :aria-pressed="!fr" @click="prefs.lang.value = 'en'">EN</button>
            <button type="button" :aria-pressed="fr" @click="prefs.lang.value = 'fr'">FR</button>
          </span>
        </div>
        <button class="demo" type="button" :disabled="!!busy" @click="demo('supervisor')">
          <span class="avatar">RK</span>
          <span><b>{{ T.demo }}</b><span>{{ T.demoSub }}</span></span>
          <CvIcon name="right" />
        </button>
        <button class="more" type="button" :aria-expanded="showRoles" @click="showRoles = !showRoles">
          {{ T.other }}<CvIcon name="down" size="s" />
        </button>
        <ul v-if="showRoles" class="roles">
          <li v-for="r in ROLE_OPTIONS.filter(x => x.role !== 'supervisor')" :key="r.role">
            <button type="button" :disabled="!!busy" @click="demo(r.role)">
              <span class="avatar">{{ initials(r.person) }}</span>
              <span><b>{{ r.person }}</b><span>{{ r.label }} · {{ r.blurb }}</span></span>
            </button>
          </li>
        </ul>
      </form>
    </main>
    <div class="quiet" aria-hidden="true">
      <LiveWave seed-key="sign-in-quiet" :source="quiet" :bar="3" :gap="3" />
    </div>
  </div>
</template>

<style scoped>
.signin { min-height: 100dvh; display: grid; grid-template-rows: 76px 1fr 140px; }
header { display: flex; align-items: center; padding: 0 40px; }
main { display: grid; place-items: center; padding: 0 16px; }
.box { width: 100%; max-width: 440px; padding: 12px 0 24px; }
h1 { font-size: 44px; font-weight: 750; letter-spacing: -0.04em; line-height: 1.02; }
.l { color: var(--cv-muted); margin: 10px 0 26px; font-size: 16px; }
label { display: block; font-size: 13px; font-weight: 700; color: var(--cv-muted); margin: 14px 0 6px; }
.err { display: flex; gap: 8px; align-items: flex-start; color: var(--cv-urgent); font-weight: 600; font-size: 14px; margin: 12px 0 0; }
.err :deep(svg) { margin-top: 3px; }
.row { display: flex; align-items: center; gap: 12px; margin-top: 22px; }
.lang { margin-left: auto; }
.demo { margin-top: 26px; width: 100%; border: 0; text-align: left; background: var(--cv-sunk); border-radius: 20px; padding: 14px 16px; font-size: 14px; display: flex; gap: 12px; align-items: center; color: var(--cv-ink); }
.demo:hover { background: var(--cv-sunk-2); }
.demo b, .roles b { display: block; }
.demo span span, .roles span span { color: var(--cv-muted); font-size: 13px; }
.demo > :deep(svg) { margin-left: auto; color: var(--cv-orchid-ink); }
.more { margin-top: 10px; border: 0; background: none; color: var(--cv-orchid-ink); font-weight: 650; font-size: 14px; display: inline-flex; gap: 4px; align-items: center; padding: 4px; }
.roles { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; }
.roles button { width: 100%; border: 0; background: var(--cv-surface); border-radius: 16px; padding: 10px 12px; display: flex; gap: 12px; align-items: center; text-align: left; font-size: 14px; color: var(--cv-ink); }
.roles button:hover { background: var(--cv-sunk); }
.quiet { height: 140px; opacity: .5; }
@media (max-width: 720px) { header { padding: 0 16px; } .signin { grid-template-rows: 64px 1fr 100px; } .quiet { height: 100px; } h1 { font-size: 38px; } }
</style>
