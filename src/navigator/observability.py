"""Structured logging with a correlation id and an installable PHI-redaction
boundary (docs/PLAN.md §5.7, §7 Phase 6).

Logging and tracing are provided by `zarreh_agentkit.observability`.
`configure_logging` here only adds the PHI redactor, through the library's
`extra_processors` hook: it lands **immediately before the renderer**, so it
scrubs the fully-assembled event dict — a developer cannot leak an identifier
into a log line by forgetting to redact at the call site.
"""

from __future__ import annotations

from zarreh_agentkit.observability import build_tracing_callbacks as build_tracing_callbacks
from zarreh_agentkit.observability import configure_logging as _configure_logging
from zarreh_agentkit.observability import get_logger as get_logger

from navigator.guardrails.redaction import PhiRedactor, redacting_processor

__all__ = ["build_tracing_callbacks", "configure_logging", "get_logger"]


def configure_logging(environment: str, redactor: PhiRedactor | None = None) -> None:
    """Configure structlog: pretty console in dev, JSON in production, with the
    correlation id merged from contextvars and PHI redacted at the boundary."""
    _configure_logging(
        environment,
        extra_processors=[] if redactor is None else [redacting_processor(redactor)],
    )
