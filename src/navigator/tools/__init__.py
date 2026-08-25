"""The tool layer: eleven store-backed tools and the scoped executor.

Every tool runs with no LLM and no network. Patient scoping, the allowlist and
the row cap are enforced in `ScopedToolExecutor`, not trusted to the model
(docs/PLAN.md §3.3, §3.4, §5.5).
"""

from navigator.tools.registry import (
    EDUCATION_TOOL_NAMES,
    LIMIT_TOOL_NAMES,
    PATIENT_SCOPED_TOOL_NAMES,
    ToolRegistry,
    build_registry,
)
from navigator.tools.scoping import ScopedToolExecutor, ToolExecution

__all__ = [
    "EDUCATION_TOOL_NAMES",
    "LIMIT_TOOL_NAMES",
    "PATIENT_SCOPED_TOOL_NAMES",
    "ScopedToolExecutor",
    "ToolExecution",
    "ToolRegistry",
    "build_registry",
]
