<script setup lang="ts">
// The avatar and its menu: who you are, Night line, caption size, Reduce motion, Activity log and sign out.
import { onClickOutside } from '@vueuse/core'
import { initials } from '~/utils/format'

const { me, signOut, can } = useSession()
const prefs = usePrefs()
const open = ref(false)
const root = ref<HTMLElement | null>(null)
onClickOutside(root, () => { open.value = false })

async function out() {
  open.value = false
  await signOut()
  await navigateTo('/sign-in')
}
</script>

<template>
  <div v-if="me" ref="root" class="acct" @keydown.escape="open = false">
    <button class="avatar" type="button" :aria-expanded="open" aria-haspopup="true" :title="`${me.user.fullName}, ${me.membership?.roleLabel ?? ''}`" @click="open = !open">
      {{ initials(me.user.fullName) }}
    </button>
    <div v-if="open" class="menu" role="menu">
      <div class="who">
        <b>{{ me.user.fullName }}</b>
        <span>{{ me.membership?.roleLabel }} · {{ me.activeOrg?.name }}</span>
      </div>
      <div class="row">
        <span>Night line</span>
        <button class="sw" type="button" role="menuitemcheckbox" :aria-checked="prefs.theme.value === 'dark'" @click="prefs.toggleTheme()">
          <CvIcon :name="prefs.theme.value === 'dark' ? 'moon' : 'sun'" size="s" />{{ prefs.theme.value === 'dark' ? 'On' : 'Off' }}
        </button>
      </div>
      <div class="row">
        <span>Caption size</span>
        <div class="seg" role="group" aria-label="Caption size">
          <button v-for="s in (['s', 'm', 'l'] as const)" :key="s" type="button" :aria-pressed="prefs.captions.value === s" @click="prefs.captions.value = s">
            {{ s.toUpperCase() }}
          </button>
        </div>
      </div>
      <div class="row">
        <span>Reduce motion</span>
        <button class="sw" type="button" role="menuitemcheckbox" :aria-checked="prefs.reduceMotionSetting.value" @click="prefs.reduceMotionSetting.value = !prefs.reduceMotionSetting.value">
          {{ prefs.reduceMotionSetting.value ? 'On' : 'Off' }}
        </button>
      </div>
      <NuxtLink v-if="can('audit:read')" to="/activity" class="item" role="menuitem" @click="open = false">
        <CvIcon name="chain" size="s" />Activity log
      </NuxtLink>
      <button class="item" type="button" role="menuitem" @click="out">
        <CvIcon name="exit" size="s" />Sign out
      </button>
    </div>
  </div>
</template>

<style scoped>
.acct { position: relative; }
.menu { position: absolute; right: 0; top: calc(100% + 8px); z-index: 50; width: 288px; background: var(--cv-surface); border-radius: 20px; box-shadow: var(--cv-shadow-float); padding: 8px; display: grid; gap: 2px; }
.who { padding: 8px 10px 10px; display: grid; }
.who b { font-family: var(--font-display); font-size: 17px; letter-spacing: -0.02em; }
.who span { color: var(--cv-muted); font-size: 13px; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 6px 4px 10px; font-size: 14px; font-weight: 600; }
.sw { display: inline-flex; align-items: center; gap: 6px; border: 0; height: 32px; padding: 0 12px; border-radius: 999px; background: var(--cv-sunk); font-weight: 650; font-size: 13px; }
.sw[aria-checked="true"] { background: var(--cv-orchid-wash); color: var(--cv-orchid-ink); }
.item { display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 10px; border-radius: 12px; border: 0; background: none; text-decoration: none; color: var(--cv-ink); font-weight: 600; font-size: 14px; text-align: left; }
.item:hover { background: var(--cv-sunk); }
</style>
