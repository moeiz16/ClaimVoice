"""Response headers on every HTTP response (including 404s for unknown routes, errors and SSE): request id, the
demo clock (X-ClaimVoice-Now), security headers and no-store for API responses.

Implemented as a Litestar `before_send` hook, which runs at the application level for every response, unlike route
middleware, which only wraps matched routes."""

from __future__ import annotations

from litestar.types import Message, Scope

from claimvoice import clock
from claimvoice.platform.errors import request_id

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"cross-origin-opener-policy", b"same-origin"),
    # The web app is served by Nuxt on :3040; the API only serves JSON, SSE, recordings and photos.
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; media-src 'self'; img-src 'self'"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=()"),
)


async def add_response_headers(message: Message, scope: Scope) -> None:
    if scope["type"] != "http" or message["type"] != "http.response.start":
        return
    headers = list(message.get("headers", []))
    names = {bytes(k).lower() for k, _ in headers}
    headers.append((b"x-request-id", request_id(scope).encode()))
    headers.append((b"x-claimvoice-now", clock.header_value().encode()))
    headers.extend(h for h in SECURITY_HEADERS if h[0] not in names)
    if scope.get("path", "").startswith("/api/") and b"cache-control" not in names:
        headers.append((b"cache-control", b"no-store"))
    message["headers"] = headers
