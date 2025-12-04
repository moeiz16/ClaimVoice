"""Response headers on every HTTP response (including 404s for unknown routes, errors and SSE): request id, the
demo clock (X-ClaimVoice-Now), security headers and no-store for API responses.

Implemented as a Litestar `before_send` hook, which runs at the application level for every response, unlike route
middleware, which only wraps matched routes."""

from __future__ import annotations

from litestar.types import ASGIApp, Message, Receive, Scope, Send

from claimvoice import clock
from claimvoice.platform.errors import ProblemError, request_id
from claimvoice.platform.ratelimit import RateLimiter, bucket_for
from claimvoice.platform.security import tokens_match
from claimvoice.platform.sessions import CSRF_COOKIE, CSRF_HEADER

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


# ---------------------------------------------------------------- CSRF and rate limits (route middleware)

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def _csrf_exempt(path: str, headers: dict[bytes, bytes]) -> bool:
    """Caller-leg endpoints use a bearer token; photo-link uploads carry their token in the URL. Neither uses
    cookies, so neither needs a CSRF token."""
    if headers.get(b"authorization", b"").lower().startswith(b"bearer "):
        return "/calls/" in path
    return path.startswith("/api/v1/photo-links/")


def guard_middleware(app: ASGIApp) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET"))
        limiter: RateLimiter | None = getattr(scope["app"].state, "limiter", None)
        bucket = bucket_for(path, method)
        if limiter is not None and bucket is not None:
            client = scope.get("client")
            ip = client[0] if client else "unknown"
            allowed, retry = limiter.hit(bucket, ip)
            if not allowed:
                raise ProblemError(
                    429,
                    "rate_limited",
                    "Too many requests",
                    "Please wait a moment and try again.",
                    headers={"Retry-After": str(retry)},
                )
        if method in _UNSAFE and path.startswith("/api/"):
            headers = dict(scope.get("headers", []))
            if not _csrf_exempt(path, headers):
                cookie = _cookie(headers.get(b"cookie", b"").decode("latin-1"), CSRF_COOKIE)
                sent = headers.get(CSRF_HEADER.encode(), b"").decode("latin-1")
                if not cookie or not sent or not tokens_match(cookie, sent):
                    raise ProblemError(403, "csrf_failed", "Security check failed", "Reload the page and try again.")
        await app(scope, receive, send)

    return middleware


def _cookie(header: str, name: str) -> str | None:
    for part in header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None
