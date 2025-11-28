from datetime import UTC, datetime

import pytest

from claimvoice.platform import audit
from claimvoice.platform.permissions import PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS, Role, has_permission


def test_every_role_has_a_label_and_only_known_permissions():
    assert set(ROLE_LABELS) == set(Role)
    for perms in ROLE_PERMISSIONS.values():
        assert perms <= set(PERMISSIONS)


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        ("supervisor", "calls:takeover", True),
        ("supervisor", "models:promote", False),
        ("compliance", "models:promote", True),
        ("adjuster", "siu:read", False),
        ("siu_investigator", "siu:decide", True),
        ("admin", "siu:read", False),
        ("intake_agent", "calls:whisper", False),
        ("nobody", "calls:read", False),
    ],
)
def test_permission_matrix(role, permission, expected):
    assert has_permission(role, permission) is expected


def _chain(n: int) -> list[dict]:
    rows, prev = [], audit.GENESIS
    for i in range(1, n + 1):
        ev = {
            "org_id": "org-1",
            "seq": i,
            "at": datetime(2026, 1, 8, 9, i, tzinfo=UTC),
            "actor_user_id": "u1",
            "actor_label": "Dana Whitford",
            "action": "call.takeover",
            "target_type": "call",
            "target_id": f"c{i}",
            "summary": "Took over a call",
            "details": {"n": i},
        }
        ev["prev_hash"] = prev
        ev["hash"] = prev = audit.chain_hash(prev, ev)
        rows.append(ev)
    return rows


def test_audit_chain_verifies_and_detects_tampering():
    rows = _chain(5)
    assert audit.verify(rows).ok
    rows[2]["summary"] = "Something else"
    check = audit.verify(rows)
    assert not check.ok and check.first_broken_seq == 3


def test_audit_chain_detects_deletion():
    rows = _chain(4)
    del rows[1]
    check = audit.verify(rows)
    assert not check.ok and check.first_broken_seq == 3
