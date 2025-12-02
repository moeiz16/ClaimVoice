"""Roles and permissions: the single source of truth (docs/API_CONTRACT.md §1.3 mirrors this table)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    INTAKE_AGENT = "intake_agent"
    ADJUSTER = "adjuster"
    SIU_INVESTIGATOR = "siu_investigator"
    COMPLIANCE = "compliance"


ROLE_LABELS: dict[Role, str] = {
    Role.ADMIN: "Administrator",
    Role.SUPERVISOR: "Claims supervisor",
    Role.INTAKE_AGENT: "Intake agent",
    Role.ADJUSTER: "Adjuster",
    Role.SIU_INVESTIGATOR: "Special investigator",
    Role.COMPLIANCE: "Compliance and quality",
}

# Every permission the API checks. Grouped by area; names are `<area>:<verb>`.
PERMISSIONS: tuple[str, ...] = (
    # switchboard and calls
    "lines:read",  # live lines, hand-off tray, surge banner (SSE stream)
    "lines:manage",  # surge controls: bring in the standby team, switch surge questions on
    "calls:read",  # call detail, transcript, timeline
    "calls:start",  # ring the line from the browser (test or demo calls)
    "calls:handoff",  # accept a hand-off and talk to the caller
    "calls:listen",  # listen in to a live call
    "calls:whisper",  # send a private note to the line (steers the next question; caller never hears it)
    "calls:takeover",  # take the call from the voice line
    "calls:hangup",  # end a live call (with a reason)
    # claims
    "claims:read",
    "claims:edit",  # correct claim-file values after the call (keeps the heard value and who changed it)
    "claims:assign",
    "claims:route",  # override the routing decision, with a reason (never an automatic denial)
    "recordings:read",  # play recordings and see unredacted-at-source photos
    "policies:read",
    # special investigations
    "siu:read",  # SIU referral detail and fraud indicators
    "siu:decide",  # accept, close or escalate an SIU referral
    # quality
    "qa:read",
    "qa:review",  # review a scored call, agree/disagree per rubric item
    # models
    "models:read",  # routing checks and their fact sheets
    "models:signoff",  # sign off a routing-check version (supervisor signs for claims, compliance for model risk)
    # administration
    "settings:read",
    "settings:manage",  # scripts, consent rules, hand-off rules, languages, retention
    "members:read",
    "members:manage",
    "audit:read",
    "org:manage",
)

_READ_CORE = {"lines:read", "calls:read", "claims:read", "policies:read", "settings:read", "members:read"}

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.ADMIN: frozenset(
        _READ_CORE
        | {
            "calls:start",
            "claims:assign",
            "qa:read",
            "models:read",
            "settings:manage",
            "members:manage",
            "audit:read",
            "org:manage",
        }
    ),
    Role.SUPERVISOR: frozenset(
        _READ_CORE
        | {
            "lines:manage",
            "calls:start",
            "calls:handoff",
            "calls:listen",
            "calls:whisper",
            "calls:takeover",
            "calls:hangup",
            "claims:edit",
            "claims:assign",
            "claims:route",
            "recordings:read",
            "qa:read",
            "qa:review",
            "models:read",
            "models:signoff",
        }
    ),
    Role.INTAKE_AGENT: frozenset(
        _READ_CORE
        | {"calls:start", "calls:handoff", "calls:takeover", "calls:hangup", "claims:edit", "recordings:read"}
    ),
    Role.ADJUSTER: frozenset(_READ_CORE | {"claims:edit", "claims:route", "recordings:read", "models:read"}),
    Role.SIU_INVESTIGATOR: frozenset(_READ_CORE | {"recordings:read", "siu:read", "siu:decide", "models:read"}),
    Role.COMPLIANCE: frozenset(
        _READ_CORE
        | {"recordings:read", "siu:read", "qa:read", "qa:review", "models:read", "models:signoff", "audit:read"}
    ),
}


def permissions_for(role: str) -> frozenset[str]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()


# Which side of a routing-check sign-off a role signs for (two different people, one per side).
SIGNOFF_SIDE: dict[Role, str] = {Role.SUPERVISOR: "claims", Role.COMPLIANCE: "model_risk"}


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for(role)
