"""RFC 7807 problem details for every error (docs/API_CONTRACT.md §1.1)."""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from litestar import Request, Response
from litestar.exceptions import HTTPException, NotFoundException, ValidationException
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from litestar.types import Scope

PROBLEM_BASE = "https://claimvoice.dev/problems/"
log = structlog.get_logger("claimvoice.errors")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def request_id(scope: Scope) -> str:
    """The request's id: the caller's X-Request-ID when well-formed, else a new one. Stable for the request."""
    state: dict[str, Any] = scope.setdefault("state", {})
    rid = state.get("request_id")
    if rid is None:
        incoming = dict(scope.get("headers", [])).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        state["request_id"] = rid
    return str(rid)


class ProblemError(Exception):
    """Raise from any handler or service; rendered as application/problem+json."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        *,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status, self.code, self.title, self.detail = status, code, title, detail
        self.errors, self.headers, self.extra = errors, headers or {}, extra or {}


def problem_response(
    request: Request[Any, Any, Any],
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    *,
    errors: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Response[dict[str, Any]]:
    body: dict[str, Any] = {"type": PROBLEM_BASE + code, "title": title, "status": status, "code": code}
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    body.update(extra or {})
    body["requestId"] = request_id(request.scope)
    return Response(content=body, status_code=status, media_type="application/problem+json", headers=headers)


def _on_problem(request: Request[Any, Any, Any], exc: ProblemError) -> Response[dict[str, Any]]:
    return problem_response(
        request, exc.status, exc.code, exc.title, exc.detail, errors=exc.errors, headers=exc.headers, extra=exc.extra
    )


def _on_validation(request: Request[Any, Any, Any], exc: ValidationException) -> Response[dict[str, Any]]:
    errors = []
    for item in exc.extra if isinstance(exc.extra, list) else []:
        if isinstance(item, dict):
            errors.append(
                {"field": str(item.get("key") or item.get("source") or ""), "message": str(item.get("message"))}
            )
    return problem_response(
        request, 422, "validation_error", "Validation failed", "One or more fields are invalid.", errors=errors
    )


def _on_not_found(request: Request[Any, Any, Any], exc: NotFoundException) -> Response[dict[str, Any]]:
    return problem_response(request, 404, "not_found", "Not found")


def _on_http(request: Request[Any, Any, Any], exc: HTTPException) -> Response[dict[str, Any]]:
    code = {
        400: "bad_request",
        401: "not_authenticated",
        403: "forbidden",
        405: "method_not_allowed",
        429: "rate_limited",
    }.get(exc.status_code, "error")
    return problem_response(request, exc.status_code, code, str(exc.detail), headers=exc.headers)


def _on_unhandled(request: Request[Any, Any, Any], exc: Exception) -> Response[dict[str, Any]]:
    log.exception("unhandled_error", path=request.url.path)
    return problem_response(request, HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Something went wrong")


EXCEPTION_HANDLERS: dict[int | type[Exception], Any] = {
    ProblemError: _on_problem,
    ValidationException: _on_validation,
    NotFoundException: _on_not_found,
    HTTPException: _on_http,
    Exception: _on_unhandled,
}
