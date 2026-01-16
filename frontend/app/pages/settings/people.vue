<script setup lang="ts">
// People: who can use Larkspur's lines and in which role, as a register; invitations as a second register. Invite
// opens a dialog.
import type { TableColumn } from '@nuxt/ui'
import type { Invitation, Member, Role } from '~/types/api'
import { api } from '~/utils/api'
import { ApiError } from '~/utils/http'
import { fmtAgo, fmtDayShort, initials } from '~/utils/format'
import { ROLE_OPTIONS } from '~/utils/labels'

const { can } = useSession()
const manage = computed(() => can('members:manage'))
const clock = useDemoClock()
const members = ref<Member[]>([])
const invites = ref<Invitation[]>([])
const loaded = ref(false)
const email = ref('')
const role = ref<Role>('intake_agent')
const msg = ref<{ ok: boolean, text: string } | null>(null)
const inviteOpen = ref(false)
const inviteError = ref<string | null>(null)
const sending = ref(false)

onMounted(async () => {
  members.value = await api.org.members()
  loaded.value = true
  if (manage.value) invites.value = await api.org.invitations().catch(() => [])
})
async function changeRole(m: Member, r: Role) {
  if (r === m.role) return
  try {
    const out = await api.org.updateMember(m.membershipId, { role: r })
    members.value = members.value.map(x => (x.membershipId === out.membershipId ? out : x))
    msg.value = { ok: true, text: `${m.fullName} is now ${out.roleLabel.toLowerCase()}.` }
  }
  catch (e) { msg.value = { ok: false, text: e instanceof ApiError && e.code === 'last_admin' ? 'Larkspur needs at least one administrator.' : 'That didn\'t change.' } }
}
function startInvite() { inviteError.value = null; inviteOpen.value = true }
async function invite() {
  sending.value = true
  inviteError.value = null
  try {
    const inv = await api.org.invite(email.value.trim(), role.value)
    invites.value = [inv, ...invites.value]
    msg.value = { ok: true, text: `Invitation sent to ${inv.email}.` }
    email.value = ''
    inviteOpen.value = false
  }
  catch (e) { inviteError.value = e instanceof ApiError ? (e.fieldError('email') ?? e.message) : 'That didn\'t send.' }
  sending.value = false
}
async function revoke(i: Invitation) {
  await api.org.revokeInvitation(i.id)
  invites.value = invites.value.map(x => (x.id === i.id ? { ...x, status: 'revoked' } : x))
}

const roleItems = ROLE_OPTIONS.map(r => ({ value: r.role, label: r.label }))
const inviteRoles = ROLE_OPTIONS.map(r => ({ value: r.role, label: r.label, description: r.blurb }))
const memberCols: TableColumn<Member>[] = [
  { accessorKey: 'fullName', header: 'Person' },
  { id: 'active', header: 'Last active', cell: ({ row }) => (row.original.lastActiveAt ? fmtAgo(row.original.lastActiveAt, clock.now.value) : '—') },
  { accessorKey: 'role', header: 'Role' },
]
const inviteCols: TableColumn<Invitation>[] = [
  { accessorKey: 'email', header: 'Invited' },
  { accessorKey: 'roleLabel', header: 'Role' },
  { id: 'sent', header: 'Sent', cell: ({ row }) => fmtDayShort(row.original.createdAt) },
  { accessorKey: 'status', header: 'Where it stands' },
  { id: 'act', header: '' },
]
const STATUS = { pending: 'Waiting', accepted: 'Joined', revoked: 'Withdrawn', expired: 'Expired' } as const
</script>

<template>
  <div>
    <section class="sec" aria-labelledby="people-h">
      <header class="head">
        <h2 id="people-h">
          People at Larkspur Mutual <UBadge color="neutral" size="md" class="num">{{ members.length }}</UBadge>
        </h2>
        <UButton v-if="manage" icon="i-lucide-user-round-plus" @click="startInvite">
          Invite someone
        </UButton>
      </header>
      <div v-if="msg" role="status">
        <CvTag :kind="msg.ok ? 'fast' : 'urgent'" :icon="msg.ok ? 'check' : 'urgent'">
          {{ msg.text }}
        </CvTag>
      </div>
      <UTable :data="members" :columns="memberCols" :loading="!loaded" class="tbl">
        <template #fullName-cell="{ row }">
          <span class="person">
            <UAvatar :text="initials(row.original.fullName)" size="md" class="bg-person-wash text-person font-bold" />
            <span class="who">
              <b>{{ row.original.fullName }}<template v-if="row.original.isYou"> (you)</template></b>
              <span>{{ row.original.title ?? row.original.email }}</span>
            </span>
          </span>
        </template>
        <template #role-cell="{ row }">
          <USelect
            v-if="manage && !row.original.isYou" :model-value="row.original.role" :items="roleItems" size="md" class="w-56"
            :aria-label="`Role for ${row.original.fullName}`" @update:model-value="(v) => changeRole(row.original, v as Role)"
          />
          <CvTag v-else kind="plain" icon="person">
            {{ row.original.roleLabel }}
          </CvTag>
        </template>
      </UTable>
    </section>

    <section v-if="manage" class="sec" aria-labelledby="inv-h">
      <h2 id="inv-h">
        Invitations
      </h2>
      <UTable :data="invites" :columns="inviteCols" class="tbl" empty="No invitations out.">
        <template #email-cell="{ row }">
          <b>{{ row.original.email }}</b>
        </template>
        <template #status-cell="{ row }">
          <CvTag :kind="row.original.status === 'pending' ? 'jade' : 'plain'" :icon="row.original.status === 'pending' ? 'clock' : 'x'">
            {{ STATUS[row.original.status] }}
          </CvTag>
        </template>
        <template #act-cell="{ row }">
          <UButton v-if="row.original.status === 'pending'" color="neutral" variant="ghost" size="md" @click="revoke(row.original)">
            Withdraw
          </UButton>
        </template>
      </UTable>
    </section>

    <UModal v-model:open="inviteOpen" title="Invite someone" description="They get an email with a link to join Larkspur Mutual's lines. The invitation is written to the activity log.">
      <template #body>
        <form id="invite-form" class="grid gap-4" @submit.prevent="invite">
          <UFormField label="Work email" name="email" required :error="inviteError ?? undefined">
            <UInput v-model="email" type="email" required placeholder="name@larkspurmutual.ca" autocomplete="off" icon="i-lucide-mail" class="w-full" autofocus />
          </UFormField>
          <UFormField label="Role" name="role">
            <USelectMenu v-model="role" :items="inviteRoles" value-key="value" :search-input="false" class="w-full" />
          </UFormField>
        </form>
      </template>
      <template #footer>
        <div class="flex gap-2 flex-wrap">
          <UButton type="submit" form="invite-form" icon="i-lucide-send" :loading="sending">
            Send the invitation
          </UButton>
          <UButton color="neutral" variant="soft" @click="inviteOpen = false">
            Not now
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.sec { padding: 20px 24px; background: var(--cv-surface); display: grid; gap: 12px; }
.head { display: flex; align-items: center; gap: 12px 20px; flex-wrap: wrap; justify-content: space-between; }
h2 { font-size: 23px; font-weight: 900; display: flex; gap: 10px; align-items: center; }
.tbl { border-top: 1px solid var(--cv-rule); }
.person { display: flex; align-items: center; gap: 12px; }
.who { display: grid; min-width: 0; }
.who span { color: var(--cv-muted); font-size: 13px; }
@media (max-width: 720px) {
  .tbl { overflow-x: auto; }
}
</style>
