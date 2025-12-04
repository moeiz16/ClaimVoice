"""Sliding-window rate limits per IP (docs/API_CONTRACT.md §1.1) and the sign-in pause per email.

In-process (one API process). Real clock: limits never move with the demo date."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

LIMITS: dict[str, tuple[int, float]] = {
    "auth": (10, 60.0),
    "public": (20, 60.0),
    "public_call": (3, 600.0),  # new public demo calls per IP per 10 minutes
    "api": (300, 60.0),
}

LOCKOUT_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60


@dataclass
class RateLimiter:
    limits: dict[str, tuple[int, float]] = field(default_factory=lambda: dict(LIMITS))
    _hits: defaultdict[tuple[str, str], deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _failures: defaultdict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def hit(self, bucket: str, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """Count one request. Returns (allowed, retry_after_seconds)."""
        limit, window = self.limits[bucket]
        t = time.monotonic() if now is None else now
        q = self._hits[(bucket, key)]
        while q and q[0] <= t - window:
            q.popleft()
        if len(q) >= limit:
            return False, max(1, int(q[0] + window - t) + 1)
        q.append(t)
        return True, 0

    # -- sign-in pause per email

    def login_paused(self, email: str, *, now: float | None = None) -> int:
        """Seconds left on the pause for this email (0 when it may try)."""
        t = time.monotonic() if now is None else now
        q = self._failures[email]
        while q and q[0] <= t - LOCKOUT_SECONDS:
            q.popleft()
        if len(q) >= LOCKOUT_FAILURES:
            return max(1, int(q[0] + LOCKOUT_SECONDS - t))
        return 0

    def login_failed(self, email: str, *, now: float | None = None) -> None:
        self._failures[email].append(time.monotonic() if now is None else now)

    def login_ok(self, email: str) -> None:
        self._failures.pop(email, None)


def bucket_for(path: str, method: str) -> str | None:
    """Which limit applies to a request path under /api/v1 (None = exempt)."""
    if not path.startswith("/api/"):
        return None
    if path.endswith("/stream") or path.endswith("/ws"):
        return None
    rest = path[len("/api/v1") :]
    if method == "POST" and (
        rest
        in {
            "/auth/login",
            "/auth/signup",
            "/auth/refresh",
            "/auth/demo",
        }
        or (rest.startswith("/invitations/") and rest.endswith("/accept"))
    ):
        return "auth"
    if rest.startswith("/photo-links/") or rest == "/demo/calls" or rest.startswith("/invitations/"):
        return "public"
    return "api"
