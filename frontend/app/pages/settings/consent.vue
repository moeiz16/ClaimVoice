<script setup lang="ts">
// Consent rules by state and province: all-party places flagged (nothing is kept until the caller says yes), the
// sentence the caller hears in each language, and what happens on "no".
import type { ConsentRule } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const { can } = useSession()
const rules = ref<ConsentRule[]>([])
const editing = ref<string | null>(null)
const draft = ref({ en: '', fr: '' })
const msg = ref<{ kind: 'ok' | 'err', text: string } | null>(null)
onMounted(async () => { try { rules.value = await api.settings.consentRules() } catch (e) { msg.value = { kind: 'err', text: (e as Error).message } } })
const sorted = computed(() => [...rules.value].sort((a, b) => (a.rule === b.rule ? a.regionLabel.localeCompare(b.regionLabel) : a.rule === 'all_party' ? -1 : 1)))

function edit(r: ConsentRule) { editing.value = r.region; draft.value = { ...r.announcement } }
async function save(r: ConsentRule) {
  try {
    const out = await api.settings.saveConsentRule(r.region, { rule: r.rule, announcement: draft.value })
    rules.value = rules.value.map(x => (x.region === out.region ? out : x))
    editing.value = null
    msg.value = { kind: 'ok', text: `Saved for ${r.regionLabel}. New calls there use it.` }
  }
  catch (e) { msg.value = { kind: 'err', text: e instanceof ApiError ? e.message : 'That didn\'t save.' } }
}
</script>

<template>
  <div class="grid">
    <p v-if="msg" class="msg" :class="msg.kind" role="status">
      <CvIcon :name="msg.kind === 'ok' ? 'check' : 'urgent'" size="s" />{{ msg.text }}
    </p>
    <section v-for="r in sorted" :key="r.region" class="card rule">
      <header>
        <h2>{{ r.regionLabel }}</h2>
        <CvTag v-if="r.rule === 'all_party'" kind="siu" icon="scale">⚖ Everyone must agree</CvTag>
        <CvTag v-else kind="plain" icon="shield">One-party: the line still announces it</CvTag>
        <span v-if="!r.isDefault" class="tag orchid">Changed by Larkspur</span>
      </header>
      <p v-if="r.rule === 'all_party'" class="strong">
        Nothing is kept until the caller says yes.
      </p>
      <p class="muted">
        {{ r.basis }}
      </p>
      <div class="said">
        <template v-if="editing === r.region">
          <label>English<textarea v-model="draft.en" class="field-input" rows="2" /></label>
          <label lang="fr">Français<textarea v-model="draft.fr" class="field-input" rows="2" /></label>
        </template>
        <template v-else>
          <p class="line">
            “{{ r.announcement.en }}”
          </p>
          <p class="line" lang="fr">
            « {{ r.announcement.fr }} »
          </p>
        </template>
      </div>
      <p class="refuse">
        <CvIcon name="x" size="s" />If they say no: {{ r.onRefusal }}
      </p>
      <div v-if="can('settings:manage')" class="acts">
        <template v-if="editing === r.region">
          <button class="btn primary sm" type="button" @click="save(r)">
            Save the sentence
          </button>
          <button class="btn soft sm" type="button" @click="editing = null">
            Cancel
          </button>
        </template>
        <button v-else class="btn soft sm" type="button" @click="edit(r)">
          Change the sentence
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; }
.msg { grid-column: 1 / -1; margin: 0; display: flex; gap: 6px; align-items: center; font-weight: 600; }
.msg.ok { color: var(--cv-fast); } .msg.err { color: var(--cv-urgent); }
.rule { padding: 18px 20px; display: grid; gap: 8px; align-content: start; }
header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-right: 4px; }
.strong { margin: 0; font-weight: 700; }
.muted { margin: 0; color: var(--cv-muted); font-size: 13.5px; }
.said { display: grid; gap: 6px; background: var(--cv-sunk); border-radius: 14px; padding: 10px 12px; }
.line { margin: 0; font-family: var(--font-display); font-size: 16.5px; font-weight: 600; letter-spacing: -0.012em; }
.said label { display: grid; gap: 4px; font-size: 12.5px; font-weight: 700; color: var(--cv-muted); }
.refuse { margin: 0; display: flex; gap: 6px; align-items: center; font-size: 13.5px; }
.acts { display: flex; gap: 8px; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
</style>
