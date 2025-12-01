"""§1.2 auth and session, §1.4 organisation, members, invitations, roles."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from claimvoice.schemas.base import ClockInfo, Lang, Model


class User(Model):
    id: str
    email: str
    full_name: str
    preferred_language: Lang
    avatar_color: str
    created_at: datetime


class OrgSummary(Model):
    id: str
    name: str
    slug: str
    role: str
    role_label: str
    is_sample: bool


class Org(Model):
    id: str
    name: str
    slug: str
    timezone: str
    regions: list[str]
    languages: list[Lang]
    is_sample: bool
    created_at: datetime


class MembershipInfo(Model):
    role: str
    role_label: str
    title: str | None
    permissions: list[str]


class SessionInfo(Model):
    expires_at: datetime
    absolute_expires_at: datetime


class Me(Model):
    user: User
    active_org: Org | None
    membership: MembershipInfo | None
    orgs: list[OrgSummary]
    session: SessionInfo
    clock: ClockInfo


class SessionState(Model):
    """GET /auth/session: always 200, for public pages."""

    me: Me | None
    clock: ClockInfo


class SignupIn(Model):
    email: str
    password: str
    full_name: str
    org_name: str
    preferred_language: Lang = "en"


class LoginIn(Model):
    email: str
    password: str


class DemoSignInIn(Model):
    role: Literal["admin", "supervisor", "intake_agent", "adjuster", "siu_investigator", "compliance"]


class SwitchOrgIn(Model):
    org_id: str


class PasswordChangeIn(Model):
    current_password: str
    new_password: str


class RefreshOut(Model):
    expires_at: datetime
    absolute_expires_at: datetime


class Member(Model):
    membership_id: str
    user_id: str
    full_name: str
    email: str
    role: str
    role_label: str
    title: str | None
    avatar_color: str
    joined_at: datetime
    last_active_at: datetime | None
    is_you: bool


class MemberUpdateIn(Model):
    role: str | None = None
    title: str | None = None


class Invitation(Model):
    id: str
    email: str
    role: str
    role_label: str
    invited_by: str | None
    created_at: datetime
    expires_at: datetime
    status: Literal["pending", "accepted", "revoked", "expired"]
    accept_url: str | None = None  # returned once, on create, in development and for the sample org only


class InvitationIn(Model):
    email: str
    role: str


class InvitationPreview(Model):
    org_name: str
    email: str
    role_label: str
    expires_at: datetime


class InvitationAcceptIn(Model):
    full_name: str
    password: str


class OrgUpdateIn(Model):
    name: str | None = None
    timezone: str | None = None
    languages: list[Lang] | None = None


class RoleInfo(Model):
    role: str
    label: str
    description: str
    permissions: list[str]
