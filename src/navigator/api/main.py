"""FastAPI application wiring (docs/PLAN.md §5.8).

Logging is configured once here. When the record store exists, the log processor
chain is seeded with a PHI redactor built from the store's own patients, so an
identifier cannot leak into a log line or a third-party trace by a forgotten
scrub at the call site (§5.7). A correlation id is bound for the duration of each
request so every log line for one request is greppable by a single id.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from navigator.api.middleware import MaxBodySizeMiddleware
from navigator.api.rate_limit import limiter
from navigator.api.routes import conversations, health, reviews
from navigator.observability import configure_logging
from navigator.settings import get_settings

settings = get_settings()


def _configure_logging_with_redaction() -> None:
    """Install the redactor only when the store it reads from exists. A fresh
    clone (before ``make data``) has no store, so logging still works without it;
    the redaction control is a property of a running deployment, not of import."""
    if Path(settings.record_db_path).exists():
        from navigator.api.deps import get_phi_redactor

        configure_logging(settings.environment, redactor=get_phi_redactor())
    else:
        configure_logging(settings.environment)


_configure_logging_with_redaction()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open one async SQLite checkpointer for the app's lifetime, so a
    suspended review survives until a clinician decides — and across a restart
    — resuming from disk rather than a lost in-memory state (docs/PLAN.md
    §5.10). The real navigator graph is built lazily against it on the first
    request (see deps.get_navigator_graph)."""
    Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as saver:
        _app.state.checkpointer = saver
        yield


app = FastAPI(
    title="Clinical Care Navigator",
    description=(
        "A patient-facing clinical assistant that is allowed to refuse. "
        "Architectural demonstration on fully synthetic Synthea data. "
        "Not a medical device. Does not diagnose."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(MaxBodySizeMiddleware, max_body_bytes=settings.max_request_body_bytes)


@app.middleware("http")
async def bind_correlation_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Binds a per-request correlation id into the structured-log context and
    echoes it back, so every log line for one request shares one id."""
    correlation_id = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")
    response.headers["X-Correlation-ID"] = correlation_id
    return response


app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(reviews.router)
