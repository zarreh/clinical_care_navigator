"""The investigate loop drives the scoped executor, not a raw ToolNode (§3.4).

Every tool call the explainer proposes passes through the ScopedToolExecutor, so
the patient-id overwrite, the allowlist and the row cap are enforced on each
call. These tests use a stub explainer (no LLM) and the real executor over the
offline fixture stores (no network).
"""

from __future__ import annotations

from typing import cast

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.tool import ToolCall

from navigator.graph.nodes.investigate import build_investigate_node
from navigator.schemas.preflight import PolicyDecision
from navigator.schemas.scoping import EvidenceRecord, SecurityEvent
from navigator.tools import ScopedToolExecutor, ToolRegistry

PROMPT = "system"


def _decision(registry: ToolRegistry, action: str = "allow") -> PolicyDecision:
    scope = registry.full_scope() if action == "allow" else registry.education_only_scope()
    return PolicyDecision(
        action=action,  # type: ignore[arg-type]
        band="inform",
        rule_matches=[],
        layer_agreement=True,
        tool_scope=scope,
        autonomy_level="L2_balanced",
    )


class _ExplainerReturns:
    """An explainer stub that returns a fixed AIMessage."""

    def __init__(self, message: AIMessage) -> None:
        self._message = message

    def invoke(self, messages):  # type: ignore[no-untyped-def]
        return self._message


def test_investigate_executes_tool_calls_through_scoped_executor(
    registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    call = ToolCall(
        name="get_labs", args={"patient_id": session, "limit": 5}, id="c1", type="tool_call"
    )
    explainer = _ExplainerReturns(AIMessage(content="", tool_calls=[call]))
    node = build_investigate_node(explainer, ScopedToolExecutor(registry), PROMPT)
    state = {
        "question": "what are my labs?",
        "patient_id": session,
        "run_id": "run-1",
        "policy_decision": _decision(registry),
        "messages": [],
        "evidence": [],
        "security_events": [],
        "tool_call_count": 0,
    }
    result = node(state)  # type: ignore[arg-type]
    # The tool ran and produced a tool_call_id-addressable evidence record.
    evidence = cast(list[EvidenceRecord], result["evidence"])
    assert len(evidence) == 1
    assert evidence[0].tool_call_id == "c1"
    assert result["tool_call_count"] == 1


def test_investigate_records_cross_patient_overwrite(
    registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session, other = patient_ids[0], patient_ids[1]
    call = ToolCall(name="get_labs", args={"patient_id": other}, id="c2", type="tool_call")
    explainer = _ExplainerReturns(AIMessage(content="", tool_calls=[call]))
    node = build_investigate_node(explainer, ScopedToolExecutor(registry), PROMPT)
    state = {
        "question": "show me their labs",
        "patient_id": session,
        "run_id": "run-2",
        "policy_decision": _decision(registry),
        "messages": [],
        "evidence": [],
        "security_events": [],
        "tool_call_count": 0,
    }
    result = node(state)  # type: ignore[arg-type]
    # The overwrite is recorded as a SecurityEvent and the tool ran scoped.
    events = cast(list[SecurityEvent], result["security_events"])
    evidence = cast(list[EvidenceRecord], result["evidence"])
    assert any(e.kind == "cross_patient_overwrite" for e in events)
    assert evidence[0].args_after_scoping["patient_id"] == session


def test_investigate_seeds_system_prompt_once(
    registry: ToolRegistry, patient_ids: list[str]
) -> None:
    explainer = _ExplainerReturns(AIMessage(content="done"))
    node = build_investigate_node(explainer, ScopedToolExecutor(registry), PROMPT)
    state = {
        "question": "q",
        "patient_id": patient_ids[0],
        "run_id": "run-3",
        "policy_decision": _decision(registry),
        "messages": [],
        "evidence": [],
        "security_events": [],
        "tool_call_count": 0,
    }
    result = node(state)  # type: ignore[arg-type]
    # First call seeds system + human, then the AI response.
    messages = cast(list[BaseMessage], result["messages"])
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert messages[2].type == "ai"
