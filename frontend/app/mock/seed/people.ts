// Larkspur Mutual's people, roles and permissions (docs/API_CONTRACT.md §1.3, docs/DATA.md "People").
import type { Invitation, Member, Role, RoleInfo } from '~/types/api'
import type { MockPerson } from '../db'
import { type Clock, P, type Who, uid } from './kit'

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Administrator',
  supervisor: 'Claims supervisor',
  intake_agent: 'Intake agent',
  adjuster: 'Adjuster',
  siu_investigator: 'Special investigator',
  compliance: 'Compliance and quality',
}

const ROLE_DESCRIPTION: Record<Role, string> = {
  admin: 'Claims operations: people, settings and the activity log.',
  supervisor: 'Runs the line desk: listens, whispers, takes over, reviews call quality, changes routes and signs routing checks for claims.',
  intake_agent: 'Takes hand-offs and the calls the line passes over.',
  adjuster: 'Works claims after the call and may change the route with a reason.',
  siu_investigator: 'Reviews closer-look referrals.',
  compliance: 'Call quality reviews, the activity log, routing-check sign-off for risk, and privacy.',
}

const EVERYONE = ['lines:read', 'calls:read', 'claims:read', 'policies:read', 'settings:read', 'members:read']

export const PERMISSIONS: Record<Role, string[]> = {
  admin: [...EVERYONE, 'calls:start', 'claims:assign', 'qa:read', 'models:read', 'settings:manage', 'members:manage', 'org:manage', 'audit:read'],
  supervisor: [
    ...EVERYONE, 'calls:start', 'lines:manage', 'calls:handoff', 'calls:takeover', 'calls:hangup', 'calls:listen',
    'calls:whisper', 'claims:edit', 'claims:assign', 'claims:route', 'recordings:read', 'qa:read', 'qa:review',
    'models:read', 'models:signoff',
  ],
  intake_agent: [...EVERYONE, 'calls:start', 'calls:handoff', 'calls:takeover', 'calls:hangup', 'claims:edit', 'recordings:read'],
  adjuster: [...EVERYONE, 'claims:edit', 'claims:route', 'recordings:read', 'models:read'],
  siu_investigator: [...EVERYONE, 'recordings:read', 'siu:read', 'siu:decide', 'models:read'],
  compliance: [...EVERYONE, 'recordings:read', 'siu:read', 'qa:read', 'qa:review', 'models:read', 'models:signoff', 'audit:read'],
}

const ROLES: Role[] = ['admin', 'supervisor', 'intake_agent', 'adjuster', 'siu_investigator', 'compliance']

interface PersonSpec { who: Who, n: number, email: string, role: Role, title: string, color: string, joined: [number, string], active: number | null }

function specs(): PersonSpec[] {
  return [
    { who: P.nadia, n: 1, email: 'nadia.kassem', role: 'admin', title: 'Claims operations manager, Calgary', color: '#7A4E9C', joined: [-38, '9:00'], active: -1 },
    { who: P.renee, n: 2, email: 'renee.kowalchuk', role: 'supervisor', title: 'Line desk supervisor, Calgary', color: '#B4436C', joined: [-38, '9:05'], active: 0 },
    { who: P.jamal, n: 3, email: 'jamal.haddad', role: 'intake_agent', title: 'Intake agent, Calgary', color: '#2F7D6D', joined: [-37, '10:15'], active: 0 },
    { who: P.sofia, n: 4, email: 'sofia.herrera', role: 'intake_agent', title: 'Intake agent, Denver', color: '#C9752B', joined: [-37, '10:20'], active: 0 },
    { who: P.aurelie, n: 5, email: 'aurelie.fortin', role: 'intake_agent', title: 'Intake agent, Montréal (French)', color: '#3D63A8', joined: [-36, '8:40'], active: 0 },
    { who: P.lena, n: 6, email: 'lena.ortiz', role: 'adjuster', title: 'Adjuster, Denver', color: '#8C5A2B', joined: [-37, '11:00'], active: 0 },
    { who: P.dev, n: 7, email: 'dev.malhotra', role: 'siu_investigator', title: 'Special investigator', color: '#4B5B6E', joined: [-36, '9:30'], active: 0 },
    { who: P.priya, n: 8, email: 'priya.sandhu', role: 'compliance', title: 'Model risk and privacy officer', color: '#6A4C93', joined: [-38, '9:10'], active: 0 },
    { who: P.owen, n: 9, email: 'owen.fairweather', role: 'compliance', title: 'Call quality lead', color: '#3F7A3A', joined: [-35, '13:30'], active: 0 },
  ]
}

const LAST_ACTIVE: Record<string, string> = {
  nadia: '16:52', renee: '7:42', jamal: '7:40', sofia: '7:38', aurelie: '7:41', lena: '7:31', dev: '7:39', priya: '7:36', owen: '7:30',
}

export interface PeopleSeed {
  people: MockPerson[]
  demoPeople: Record<Role, string>
  permissions: Record<Role, string[]>
  roles: RoleInfo[]
  members: Member[]
  invitations: Invitation[]
}

export function buildPeople(c: Clock): PeopleSeed {
  const list = specs()
  const people: MockPerson[] = list.map(s => ({
    userId: s.who.id,
    membershipId: uid('membership', s.n),
    fullName: s.who.name,
    email: `${s.email}@larkspurmutual.ca`,
    role: s.role,
    roleLabel: ROLE_LABEL[s.role],
    title: s.title,
    avatarColor: s.color,
  }))
  const members: Member[] = list.map((s) => {
    const key = s.email.split('.')[0] ?? ''
    const last = LAST_ACTIVE[key]
    return {
      membershipId: uid('membership', s.n),
      userId: s.who.id,
      fullName: s.who.name,
      email: `${s.email}@larkspurmutual.ca`,
      role: s.role,
      roleLabel: ROLE_LABEL[s.role],
      title: s.title,
      avatarColor: s.color,
      joinedAt: c.atIso(s.joined[0], s.joined[1]),
      lastActiveAt: last && s.active != null ? c.atIso(s.active, last) : null,
      isYou: false,
    }
  }).sort((a, b) => a.fullName.localeCompare(b.fullName))

  const invitations: Invitation[] = [
    {
      id: uid('invite', 1),
      email: 'tanvir.ahmed@larkspurmutual.ca',
      role: 'intake_agent',
      roleLabel: ROLE_LABEL.intake_agent,
      invitedBy: P.nadia.name,
      createdAt: c.atIso(-2, '13:04'),
      expiresAt: c.atIso(5, '13:04'),
      status: 'pending',
      acceptUrl: null,
    },
    {
      id: uid('invite', 2),
      email: 'claire.beaulieu@larkspurmutual.ca',
      role: 'adjuster',
      roleLabel: ROLE_LABEL.adjuster,
      invitedBy: P.nadia.name,
      createdAt: c.atIso(-1, '11:32'),
      expiresAt: c.atIso(6, '11:32'),
      status: 'pending',
      acceptUrl: null,
    },
  ]

  return {
    people,
    demoPeople: {
      admin: P.nadia.id,
      supervisor: P.renee.id,
      intake_agent: P.jamal.id,
      adjuster: P.lena.id,
      siu_investigator: P.dev.id,
      compliance: P.priya.id,
    },
    permissions: PERMISSIONS,
    roles: ROLES.map(role => ({ role, label: ROLE_LABEL[role], description: ROLE_DESCRIPTION[role], permissions: PERMISSIONS[role] })),
    members,
    invitations,
  }
}
