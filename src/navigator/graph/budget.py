"""Per-run cost guardrail (docs/PLAN.md §5.5).

On breach the run terminates with a conservative templated response and the
reason recorded — it never silently truncates a clinical answer. Row caps
live in the store and the scoped executor; this guardrail bounds the
*loop*: how many tool calls and how much wall-clock one run may consume.

The ceiling and breach check are `zarreh_agentkit.guardrails.budget`
(extracted here and in A2, converging on an identical shape); this module
only supplies this service's own default ceiling. The breach *response* — a
conservative templated answer, never a silent truncation — stays local, per
HARVEST #12's "ceiling shared, response not" split.
"""

from __future__ import annotations

from zarreh_agentkit.guardrails.budget import Budget
from zarreh_agentkit.guardrails.budget import budget_breach_reason as _budget_breach_reason

__all__ = ["Budget", "DEFAULT_BUDGET", "budget_breach_reason"]

DEFAULT_BUDGET = Budget(max_tool_calls=12, max_wall_clock_seconds=90.0)


def budget_breach_reason(
    tool_call_count: int, started_at: float, budget: Budget = DEFAULT_BUDGET
) -> str | None:
    """A human-readable breach reason, or None if within budget."""
    return _budget_breach_reason(tool_call_count, started_at, budget)
