<script setup lang="ts">
// People: who can use Larkspur's lines and in which role; invitations.
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
const email = ref('')
const role = ref<Role>('intake_agent')
const msg = ref<{ ok: boolean, text: string } | null>(null)

onMounted(async () => {
  members.value = await api.org.members()
  if (manage.value) invites.value = await api.org.invitations().catch(() => [])
})
async function changeRole(m: Member, r: Role) {
  try {
    const out = await api.org.updateMember(m.membershipId, { role: r })
    members.value = members.value.map(x => (x.membershipId === out.membershipId ? out : x))
    msg.value = { ok: true, text: `${m.fullName} is now ${out.roleLabel.toLowerCase()}.` }
  }
  catch (e) { msg.value = { ok: false, text: e instanceof ApiError && e.code === 'last_admin' ? 'Larkspur needs at least one administrator.' : 'That didn\'t change.' } }
}
async function invite() {
  try {
    const inv = await api.org.invite(email.value.trim(), role.value)
    invites.value = [inv, ...invites.value]
    msg.value = { ok: true, text: `Invitation sent to ${inv.email}.` }
    email.value = ''
  }
  catch (e) { msg.value = { ok: false, text: e instanceof ApiError ? (e.fieldError('email') ?? e.message) : 'That didn\'t send.' } }
}
async function revoke(i: Invitation) {
  await api.org.revokeInvitation(i.id)
  invites.value = invites.value.map(x => (x.id === i.id ? { ...x, status: 'revoked' } : x))
}
</script>

<template>
  <div class="grid">
    <section class="card body">
      <h2>People at Larkspur Mutual <span class="n num">{{ members.length }}</span></h2>
      <p v-if="msg" class="msg" :class="msg.ok ? 'ok' : 'err'" role="status">
        <CvIcon :name="msg.ok ? 'check' : 'urgent'" size="s" />{{ msg.text }}
      </p>
      <ul class="people">
        <li v-for="m in members" :key="m.membershipId">
          <span class="avatar">{{ initials(m.fullName) }}</span>
          <span class="who"><b>{{ m.fullName }}<template v-if="m.isYou"> (you)</template></b><span>{{ m.title ?? m.email }}<template v-if="m.lastActiveAt"> · active {{ fmtAgo(m.lastActiveAt, clock.now.value) }}</template></span></span>
          <select v-if="manage && !m.isYou" class="inline-blank" :value="m.role" :aria-label="`Role for ${m.fullName}`" @change="changeRole(m, ($event.target as HTMLSelectElement).value as Role)">
            <option v-for="r in ROLE_OPTIONS" :key="r.role" :value="r.role">{{ r.label }}</option>
          </select>
          <span v-else class="tag plain">{{ m.roleLabel }}</span>
        </li>
      </ul>
    </section>
    <section v-if="manage" class="card tint body">
      <h2>Invite someone</h2>
      <form class="inv" @submit.prevent="invite">
        <label for="inv-email">Work email</label>
        <input id="inv-email" v-model="email" class="field-input sm" type="email" required placeholder="name@larkspurmutual.ca">
        <label for="inv-role">Role</label>
        <select id="inv-role" v-model="role" class="field-input sm">
          <option v-for="r in ROLE_OPTIONS" :key="r.role" :value="r.role">{{ r.label }} · {{ r.blurb }}</option>
        </select>
        <button class="btn primary sm" type="submit">
          <CvIcon name="send" size="s" />Send the invitation
        </button>
      </form>
      <h3>Invitations</h3>
      <ul class="invites">
        <li v-for="i in invites" :key="i.id">
          <span class="who"><b>{{ i.email }}</b><span>{{ i.roleLabel }} · sent {{ fmtDayShort(i.createdAt) }}</span></span>
          <CvTag :kind="i.status === 'pending' ? 'orchid' : 'plain'" :icon="i.status === 'pending' ? 'clock' : 'x'">{{ i.status === 'pending' ? 'Waiting' : i.status === 'accepted' ? 'Joined' : i.status === 'revoked' ? 'Withdrawn' : 'Expired' }}</CvTag>
          <button v-if="i.status === 'pending'" class="btn quiet sm" type="button" @click="revoke(i)">
            Withdraw
          </button>
        </li>
        <li v-if="!invites.length" class="muted">
          No invitations out.
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 14px; align-items: start; }
.body { padding: 18px 22px 22px; display: grid; gap: 10px; }
h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; display: flex; gap: 8px; align-items: center; }
h3 { font-family: var(--font-sans); font-size: 13px; font-weight: 750; color: var(--cv-muted); letter-spacing: 0; margin-top: 8px; }
.n { font-family: var(--font-sans); font-size: 13px; background: var(--cv-sunk); border-radius: 999px; padding: 2px 10px; }
.msg { margin: 0; display: flex; gap: 6px; align-items: center; font-weight: 600; font-size: 14px; }
.msg.ok { color: var(--cv-fast); } .msg.err { color: var(--cv-urgent); }
.people, .invites { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.people li, .invites li { display: flex; align-items: center; gap: 12px; padding: 8px 10px; border-radius: 14px; background: var(--cv-sunk); }
.invites li { background: var(--cv-surface); }
.who { display: grid; flex: 1; min-width: 0; }
.who span { color: var(--cv-muted); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inline-blank { font-family: var(--font-sans); font-size: 14px; }
.inv { display: grid; gap: 6px; }
.inv label { font-size: 13px; font-weight: 700; color: var(--cv-muted); }
.inv .btn { justify-self: start; margin-top: 6px; }
.muted { color: var(--cv-muted); font-size: 14px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
