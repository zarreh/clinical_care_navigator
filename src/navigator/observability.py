"""Structured logging with a correlation id and an installable PHI-redaction
boundary (docs/PLAN.md §5.7, §7 Phase 6).

`get_logger` is byte-identical to `zarreh_agentkit.observability.get_logger`
and is re-exported from there. `configure_logging` is *not* re-exported: it
needs an optional `redactor` hook the kit's version has no reason to carry
(only this service needs PHI redaction so far — HARVEST.md's "incidental"
call on this row was wrong for this half of it), so the processor chain
stays local. It places the redacting processor **immediately before the
renderer**, so it scrubs the fully-assembled event dict — a developer cannot
leak an identifier into a log line by forgetting to redact at the call site.
"""

from __future__ import annotations

import structlog
from zarreh_agentkit.observability import get_logger as get_logger

from navigator.guardrails.redaction import PhiRedactor, redacting_processor

__all__ = ["configure_logging", "get_logger"]


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
