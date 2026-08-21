"""Enforces a maximum request body size at the ASGI level (docs/PLAN.md §7
Phase 6) — this API is internet-facing, so an unbounded body is a
resource-exhaustion vector regardless of what `Content-Length` claims.

Rejects oversized requests here, before the request reaches FastAPI's routing:
FastAPI wraps arbitrary exceptions raised while reading the body into a generic
400, so raising from inside a wrapped `receive()` cannot produce an honest 413.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Buffers the body itself (bounded to `max_body_bytes` plus one chunk) so
    the cap holds even when `Content-Length` is absent or understates the truth,
    then replays the buffered body to the wrapped app unchanged."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total_bytes = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                break
            body = message.get("body", b"")
            total_bytes += len(body)
            if total_bytes > self._max_body_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body exceeds {self._max_body_bytes} bytes"},
                )
                await response(scope, receive, send)
                return
            chunks.append(body)
            more_body = message.get("more_body", False)

        buffered_body = b"".join(chunks)
        already_replayed = False

        async def replay_receive() -> Message:
            nonlocal already_replayed
            if not already_replayed:
                already_replayed = True
                return {"type": "http.request", "body": buffered_body, "more_body": False}
            return await receive()

        await self._app(scope, replay_receive, send)
