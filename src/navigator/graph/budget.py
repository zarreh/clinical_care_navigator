"""Per-run cost guardrail (docs/PLAN.md §5.5).

On breach the run terminates with a conservative templated response and the
reason recorded — it never silently truncates a clinical answer. Row caps live
in the store and the scoped executor; this guardrail bounds the *loop*: how many
tool calls and how much wall-clock one run may consume.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    max_tool_calls: int = 12
    max_wall_clock_seconds: float = 90.0


DEFAULT_BUDGET = Budget()


def budget_breach_reason(
    tool_call_count: int, started_at: float, budget: Budget = DEFAULT_BUDGET
) -> str | None:
    """A human-readable breach reason, or None if within budget."""
    if tool_call_count > budget.max_tool_calls:
        return f"exceeded max_tool_calls={budget.max_tool_calls} (used {tool_call_count})"
    elapsed = time.time() - started_at
    if elapsed > budget.max_wall_clock_seconds:
        return (
            f"exceeded max_wall_clock_seconds={budget.max_wall_clock_seconds} "
            f"(elapsed {elapsed:.1f}s)"
        )
    return None
