"""Prometheus metrics (docs/API_CONTRACT.md §1.13): requests, live calls, per-turn response time, tool timeouts and
SSE subscribers. Labels never carry personal data or ids."""

from __future__ import annotations

import time

from litestar.types import ASGIApp, Message, Receive, Scope, Send
from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter("claimvoice_http_requests_total", "HTTP requests", ["method", "status"])
DURATION = Histogram(
    "claimvoice_http_request_seconds", "HTTP request duration", ["method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)  # fmt: skip
LIVE_CALLS = Gauge("claimvoice_live_calls", "Calls on the line right now")
TURN_SECONDS = Histogram(
    "claimvoice_turn_response_seconds", "End of caller speech to the line's first audio or caption",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0),
)  # fmt: skip
TOOL_TIMEOUTS = Counter("claimvoice_tool_timeouts_total", "Mid-call lookups that ran past their budget", ["tool"])
SSE_SUBSCRIBERS = Gauge("claimvoice_sse_subscribers", "Open line-desk and call streams")


def metrics_middleware(app: ASGIApp) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or str(scope.get("path", "")).endswith("/stream"):
            await app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await app(scope, receive, capture)
        finally:
            method = str(scope.get("method", "GET"))
            REQUESTS.labels(method, str(status)).inc()
            DURATION.labels(method).observe(time.perf_counter() - started)

    return middleware
