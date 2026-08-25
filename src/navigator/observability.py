"""Structured logging with a correlation id and an installable PHI-redaction
boundary (docs/PLAN.md §5.7, §7 Phase 6).

`configure_logging` builds the structlog processor chain; when a `PhiRedactor`
is supplied the redacting processor is placed **immediately before the
renderer**, so it scrubs the fully-assembled event dict — a developer cannot
leak an identifier into a log line by forgetting to redact at the call site.
"""

from __future__ import annotations

import structlog

from navigator.guardrails.redaction import PhiRedactor, redacting_processor


def configure_logging(environment: str, redactor: PhiRedactor | None = None) -> None:
    """Configure structlog: pretty console in dev, JSON in production, with the
    correlation id merged from contextvars and PHI redacted at the boundary."""
    renderer = (
        structlog.dev.ConsoleRenderer()
        if environment == "development"
        else structlog.processors.JSONRenderer()
    )
    processors: list[object] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if redactor is not None:
        processors.append(redacting_processor(redactor))
    processors.append(renderer)
    structlog.configure(processors=processors)  # type: ignore[arg-type]


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
