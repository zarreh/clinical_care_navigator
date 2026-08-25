"""The budget guardrail terminates a runaway run conservatively (§5.5)."""

from __future__ import annotations

import time

from navigator.graph.budget import Budget, budget_breach_reason
from navigator.graph.edges import route_after_investigate
from navigator.graph.nodes.budget_exceeded import budget_exceeded_node
from navigator.graph.state import NavigatorState
from navigator.schemas.answer import PatientAnswer


def test_within_budget_returns_none() -> None:
    assert budget_breach_reason(3, time.time(), Budget()) is None


def test_tool_call_breach() -> None:
    reason = budget_breach_reason(13, time.time(), Budget(max_tool_calls=12))
    assert reason is not None and "max_tool_calls" in reason


def test_wall_clock_breach() -> None:
    reason = budget_breach_reason(0, time.time() - 200, Budget(max_wall_clock_seconds=90.0))
    assert reason is not None and "max_wall_clock_seconds" in reason


def test_route_to_budget_exceeded_on_breach() -> None:
    state: NavigatorState = {
        "tool_call_count": 13,
        "started_at": time.time(),
        "messages": [],
    }
    assert route_after_investigate(state) == "budget_exceeded"


def test_budget_exceeded_node_returns_conservative_template() -> None:
    result = budget_exceeded_node({"autonomy_level": "L2_balanced"})
    answer = result["draft"]
    assert isinstance(answer, PatientAnswer)
    assert answer.disposition == "templated"
    assert answer.claims == []
    # Conservative: routes to the care team, never fabricates an answer.
    assert "care team" in answer.body.lower() or "clinician" in answer.body.lower()
