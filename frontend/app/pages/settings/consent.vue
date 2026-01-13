<script setup lang="ts">
// Consent rules by state and province, as a register: all-party places flagged first (nothing is kept until the
// caller says yes), the sentence the caller hears in each language, and what happens on "no". Changing a sentence
// opens a dialog.
import type { TableColumn } from '@nuxt/ui'
import type { ConsentRule } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'

const { can } = useSession()
const manage = computed(() => can('settings:manage'))
const rules = ref<ConsentRule[]>([])
const loaded = ref(false)
const editing = ref<ConsentRule | null>(null)
const draft = ref({ en: '', fr: '' })
const busy = ref(false)
const msg = ref<{ kind: 'ok' | 'err', text: string } | null>(null)
onMounted(async () => {
  try { rules.value = await api.settings.consentRules() }
  catch (e) { msg.value = { kind: 'err', text: (e as Error).message } }
  loaded.value = true
})
const sorted = computed(() => [...rules.value].sort((a, b) => (a.rule === b.rule ? a.regionLabel.localeCompare(b.regionLabel) : a.rule === 'all_party' ? -1 : 1)))

const cols = computed<TableColumn<ConsentRule>[]>(() => [
  { accessorKey: 'regionLabel', header: 'Where the caller is' },
  { accessorKey: 'rule', header: 'Who must agree' },
  { id: 'heard', header: 'What the caller hears' },
  { accessorKey: 'onRefusal', header: 'If they say no' },
  ...(manage.value ? [{ id: 'act', header: '' }] : []),
])

const open = computed({ get: () => !!editing.value, set: (v: boolean) => { if (!v) editing.value = null } })
function edit(r: ConsentRule) { editing.value = r; draft.value = { ...r.announcement } }
async function save() {
  const r = editing.value
  if (!r) return
  busy.value = true
  try {
    const out = await api.settings.saveConsentRule(r.region, { rule: r.rule, announcement: draft.value })
    rules.value = rules.value.map(x => (x.region === out.region ? out : x))
    editing.value = null
    msg.value = { kind: 'ok', text: `Saved for ${r.regionLabel}. New calls there use it.` }
  }
  catch (e) { msg.value = { kind: 'err', text: e instanceof ApiError ? e.message : 'That didn\'t save.' } }
  busy.value = false
}
</script>

<template>
  <div>
    <div v-if="msg" class="msg" role="status">
      <CvTag :kind="msg.kind === 'ok' ? 'fast' : 'urgent'" :icon="msg.kind === 'ok' ? 'check' : 'urgent'">
        {{ msg.text }}
      </CvTag>
    </div>

    <section class="doc" aria-label="Consent rules">
      <UTable :data="sorted" :columns="cols" :loading="!loaded" class="tbl" :ui="{ td: 'align-top whitespace-normal' }">
        <template #regionLabel-cell="{ row }">
          <p class="place">
            {{ row.original.regionLabel }}
          </p>
          <p class="basis">
            {{ row.original.basis }}
          </p>
          <CvTag v-if="!row.original.isDefault" kind="orchid" icon="i-lucide-pencil" class="mt-1.5">
            Changed by Larkspur
          </CvTag>
        </template>
        <template #rule-cell="{ row }">
          <template v-if="row.original.rule === 'all_party'">
            <CvTag kind="siu" icon="scale" class="whitespace-nowrap">
              ⚖ Everyone must agree
            </CvTag>
            <p class="strong">
              Nothing is kept until the caller says yes.
            </p>
          </template>
          <CvTag v-else kind="plain" icon="shield">
            One-party: the line still announces it
          </CvTag>
        </template>
        <template #heard-cell="{ row }">
          <p class="line">
            “{{ row.original.announcement.en }}”
          </p>
          <p class="line" lang="fr">
            « {{ row.original.announcement.fr }} »
          </p>
        </template>
        <template #onRefusal-cell="{ row }">
          <span class="refuse"><UIcon name="i-lucide-x" class="size-4 shrink-0" />{{ row.original.onRefusal }}</span>
        </template>
        <template #act-cell="{ row }">
          <UButton color="neutral" variant="soft" size="md" icon="i-lucide-pencil" @click="edit(row.original)">
            Change the sentence
          </UButton>
        </template>
      </UTable>
    </section>

    <UModal v-model:open="open" :title="editing ? `The sentence callers hear in ${editing.regionLabel}` : 'Change the sentence'" description="New calls there use it once you save. The change is written to the activity log.">
      <template #body>
        <div class="grid gap-4">
          <UFormField label="English" name="en">
            <UTextarea v-model="draft.en" :rows="3" autoresize class="w-full" />
          </UFormField>
          <UFormField label="Français" name="fr" lang="fr">
            <UTextarea v-model="draft.fr" :rows="3" autoresize class="w-full" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex gap-2 flex-wrap">
          <UButton icon="i-lucide-check" :loading="busy" @click="save">
            Save the sentence
          </UButton>
          <UButton color="neutral" variant="soft" @click="editing = null">
            Cancel
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.msg { padding: 12px 32px; border-bottom: 1px solid var(--cv-rule); }
.doc { padding: 0 32px 24px; }
.place { margin: 0; font-family: var(--font-voice); font-variation-settings: "FLAR" 100; font-size: 18px; font-weight: 680; }
.basis { margin: 2px 0 0; color: var(--cv-muted); font-size: 13px; max-width: 280px; }
.strong { margin: 6px 0 0; font-weight: 650; font-size: 13.5px; }
.line { margin: 0 0 4px; font-family: var(--font-voice); font-variation-settings: "FLAR" 60; font-size: 16px; font-weight: 560; line-height: 1.35; max-width: 460px; }
.refuse { display: inline-flex; gap: 6px; align-items: flex-start; font-size: 13.5px; }
.refuse :deep(svg), .refuse > span:first-child { margin-top: 2px; }
@media (max-width: 720px) {
  .msg { padding: 10px 16px; }
  .doc { padding: 0 16px 20px; overflow-x: auto; }
}
</style>
