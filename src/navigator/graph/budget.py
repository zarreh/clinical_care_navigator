"""Per-run cost guardrail (docs/PLAN.md §5.5).

The ceiling comes from `zarreh_agentkit.guardrails.budget`; the *response* to a
breach is A3's own: the run terminates with a conservative templated response and
the reason recorded — it never silently truncates a clinical answer. Row caps live
in the store and the scoped executor; this bounds the *loop*.
"""

from zarreh_agentkit.guardrails.budget import Budget, budget_breach_reason

# Tighter than the library default (15 calls / 120s): a patient is waiting.
DEFAULT_BUDGET = Budget(max_tool_calls=12, max_wall_clock_seconds=90.0)

__all__ = ["DEFAULT_BUDGET", "Budget", "budget_breach_reason"]
