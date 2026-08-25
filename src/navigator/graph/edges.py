"""Routing predicates — one small function each (docs/PLAN.md §9.3).

The pre-flight gate routes on the `PolicyDecision.action`: the four non-`allow`
branches go straight to their templated response and never reach a patient tool
(§3.3); `allow` proceeds to the investigate loop. The investigate loop routes
back to itself while the explainer is still making tool calls, onward to
`draft_answer` when it stops, or to a conservative template if the budget
guardrail trips (§5.5).
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage

from navigator.graph.budget import DEFAULT_BUDGET, budget_breach_reason
from navigator.graph.state import NavigatorState

TemplateBranch = Literal["emergency", "crisis", "out_of_scope", "clinician_review", "allow"]

_ACTION_TO_BRANCH: dict[str, TemplateBranch] = {
    "direct_to_emergency_care": "emergency",
    "crisis": "crisis",
    "out_of_scope": "out_of_scope",
    "clinician_review": "clinician_review",
    "allow": "allow",
}


def route_after_resolve_policy(state: NavigatorState) -> TemplateBranch:
    """Route on the pre-flight action. Non-`allow` never reaches a patient tool."""
    decision = state["policy_decision"]
    return _ACTION_TO_BRANCH[decision.action]


def route_after_post_flight(
    state: NavigatorState,
) -> Literal["publish", "escalate", "review", "investigate"]:
    """Route on the post-flight disposition (§5.3).

    `publish` -> the deterministic publish node; `escalate` -> the templated
    override (critical value / out-of-scope); `review` -> the clinician review
    queue; `loop` -> back into the investigate loop to gather the missing
    citation. `loop` is mapped to `investigate` because that is the node that
    re-gathers evidence after the citation feedback is appended.
    """
    disposition = state["post_flight"].disposition
    if disposition == "loop":
        return "investigate"
    return disposition


def route_after_investigate(
    state: NavigatorState,
) -> Literal["investigate", "draft_answer", "budget_exceeded"]:
    """Continue the loop, draft, or terminate conservatively on budget breach."""
    if (
        budget_breach_reason(state.get("tool_call_count", 0), state["started_at"], DEFAULT_BUDGET)
        is not None
    ):
        return "budget_exceeded"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "investigate"
    return "draft_answer"
