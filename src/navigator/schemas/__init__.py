"""Typed boundaries: tool arguments, tool results and executor records.

The lowest layer in the import graph -- schemas depend on nothing in the
application (docs/PLAN.md §9.3). Tool results are Pydantic models so the boundary
is checked in both directions, unlike the source notebook's JSON strings (§3.6).
"""

from navigator.schemas.scoping import (
    EvidenceRecord,
    SecurityEvent,
    SecurityEventKind,
    ToolScope,
)

__all__ = [
    "EvidenceRecord",
    "SecurityEvent",
    "SecurityEventKind",
    "ToolScope",
]
