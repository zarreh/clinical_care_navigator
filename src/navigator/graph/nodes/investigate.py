"""The investigate ReAct step (docs/PLAN.md §5.1).

One step of the loop: the tool-bound explainer proposes tool calls, and the
**scoped executor** runs them. This is the deliberate difference from the source
notebook and from a raw LangGraph `ToolNode`: every tool call passes through
`ScopedToolExecutor`, so the patient-id overwrite, the allowlist, the row cap
and the `SecurityEvent` record are enforced on each call (§3.3, §3.4) — not
trusted to the model.

The loop itself (investigate ⇄ tools) is driven by the edge predicate in
`edges.py`, which routes back here while the explainer is still making tool
calls and onward to `draft_answer` when it stops, or to a conservative template
if the budget guardrail trips (§5.5).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from navigator.graph.agents.explainer import Explainer
from navigator.graph.state import NavigatorState
from navigator.tools.scoping import ScopedToolExecutor


def _seed_messages(state: NavigatorState, system_prompt: str) -> list[BaseMessage]:
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["question"]),
    ]


def build_investigate_node(
    explainer: Explainer,
    executor: ScopedToolExecutor,
    system_prompt: str,
) -> Callable[[NavigatorState], dict[str, object]]:
    def investigate_node(state: NavigatorState) -> dict[str, object]:
        seed = [] if state.get("messages") else _seed_messages(state, system_prompt)
        conversation = [*state.get("messages", []), *seed]
        response = explainer.invoke(conversation)

        decision = state["policy_decision"]
        tool_calls = getattr(response, "tool_calls", None) or []
        execution = executor.execute(
            tool_calls,
            patient_id=state["patient_id"],
            scope=decision.tool_scope,
            run_id=state["run_id"],
        )

        return {
            "messages": [*seed, response, *execution.messages],
            "evidence": [*state.get("evidence", []), *execution.evidence],
            "security_events": [*state.get("security_events", []), *execution.security_events],
            "tool_call_count": state.get("tool_call_count", 0) + len(tool_calls),
        }

    return investigate_node
