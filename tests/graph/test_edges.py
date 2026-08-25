"""Routing predicates (§5.1): non-allow never reaches a patient tool (§3.3)."""

from __future__ import annotations

import time

from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall

from navigator.graph.edges import route_after_investigate, route_after_resolve_policy
from navigator.graph.state import NavigatorState
from navigator.schemas.preflight import PolicyDecision
from navigator.schemas.scoping import ToolScope


def _decision(action: str) -> PolicyDecision:
    return PolicyDecision(
        action=action,  # type: ignore[arg-type]
        band="inform",
        rule_matches=[],
        layer_agreement=True,
        tool_scope=ToolScope(allowed_tool_names=frozenset(), row_cap=25),
        autonomy_level="L2_balanced",
    )


def test_resolve_policy_routes_each_action() -> None:
    def route(action: str) -> str:
        state: NavigatorState = {"policy_decision": _decision(action)}
        return route_after_resolve_policy(state)

    assert route("direct_to_emergency_care") == "emergency"
    assert route("crisis") == "crisis"
    assert route("out_of_scope") == "out_of_scope"
    assert route("clinician_review") == "clinician_review"
    assert route("allow") == "allow"


def test_investigate_loops_while_tool_calls() -> None:
    msg = AIMessage(
        content="", tool_calls=[ToolCall(name="get_labs", args={}, id="c", type="tool_call")]
    )
    state = {"messages": [msg], "tool_call_count": 1, "started_at": time.time()}
    assert route_after_investigate(state) == "investigate"  # type: ignore[arg-type]


def test_investigate_drafts_when_no_tool_calls() -> None:
    state = {
        "messages": [AIMessage(content="done")],
        "tool_call_count": 1,
        "started_at": time.time(),
    }
    assert route_after_investigate(state) == "draft_answer"  # type: ignore[arg-type]


def test_post_flight_routes_each_disposition() -> None:
    from navigator.graph.edges import route_after_post_flight
    from navigator.schemas.postflight import PostFlightResult

    def route(disposition: str) -> str:
        state: NavigatorState = {
            "post_flight": PostFlightResult(disposition=disposition)  # type: ignore[arg-type]
        }
        return route_after_post_flight(state)

    assert route("publish") == "publish"
    assert route("escalate") == "escalate"
    assert route("review") == "review"
    # A citation loop routes back into the investigate loop to re-gather evidence.
    assert route("loop") == "investigate"
