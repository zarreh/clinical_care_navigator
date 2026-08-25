"""The scoped executor enforces the four Phase 2 controls (docs/PLAN.md §3.3-§3.4).

These are the exit criteria as tests: a cross-patient argument is overwritten
*and recorded*; an out-of-scope call under a restricted `ToolScope` is refused at
the executor; an unknown tool is blocked; and every result is addressable by its
`tool_call_id`. Cross-patient access is a test, not a metric -- it must be 100%
because it is code (§8).
"""

from __future__ import annotations

from langchain_core.messages.tool import ToolCall

from navigator.schemas.scoping import ToolScope
from navigator.tools import ScopedToolExecutor, ToolRegistry

RUN_ID = "run-under-test"


def _call(name: str, call_id: str, **args: object) -> ToolCall:
    return ToolCall(name=name, args=dict(args), id=call_id, type="tool_call")


def test_normal_call_produces_addressable_evidence(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    result = executor.execute(
        [_call("get_labs", "call-1", patient_id=session)],
        patient_id=session,
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    assert not result.security_events
    assert len(result.evidence) == 1
    # Every result is tool_call_id-addressable: the evidence record and the
    # message both carry the same id.
    by_id = {record.tool_call_id: record for record in result.evidence}
    assert "call-1" in by_id
    assert result.messages[0].tool_call_id == "call-1"
    assert by_id["call-1"].tool_name == "get_labs"


def test_cross_patient_argument_is_overwritten_and_recorded(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session, other = patient_ids[0], patient_ids[1]
    result = executor.execute(
        [_call("get_labs", "call-2", patient_id=other)],
        patient_id=session,
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    # Recorded.
    assert len(result.security_events) == 1
    event = result.security_events[0]
    assert event.kind == "cross_patient_overwrite"
    assert event.requested == other
    assert event.enforced == session
    assert event.run_id == RUN_ID
    # Overwritten: the tool actually ran against the session patient.
    assert result.evidence[0].args_after_scoping["patient_id"] == session
    assert result.evidence[0].result["patient_id"] == session


def test_matching_patient_id_raises_no_event(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    result = executor.execute(
        [_call("get_labs", "call-3", patient_id=session)],
        patient_id=session,
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    assert not result.security_events


def test_out_of_scope_call_is_refused_at_the_executor(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    # A restricted scope from which patient tools are absent (a non-`allow`
    # gate decision, §3.3).
    result = executor.execute(
        [_call("get_labs", "call-4", patient_id=session)],
        patient_id=session,
        scope=registry.education_only_scope(),
        run_id=RUN_ID,
    )
    assert not result.evidence  # the tool never ran
    assert len(result.security_events) == 1
    assert result.security_events[0].kind == "out_of_scope_tool"
    assert result.messages[0].status == "error"
    assert result.messages[0].tool_call_id == "call-4"


def test_education_tool_is_reachable_under_restricted_scope(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    result = executor.execute(
        [_call("lookup_lab_education", "call-5", loinc_code="18262-6")],
        patient_id=patient_ids[0],
        scope=registry.education_only_scope(),
        run_id=RUN_ID,
    )
    assert not result.security_events
    assert len(result.evidence) == 1


def test_unknown_tool_is_blocked_and_recorded(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    result = executor.execute(
        [_call("drop_all_tables", "call-6")],
        patient_id=patient_ids[0],
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    assert not result.evidence
    assert len(result.security_events) == 1
    assert result.security_events[0].kind == "blocked_unknown_tool"
    assert result.messages[0].status == "error"


def test_row_cap_clamps_limit(registry: ToolRegistry, patient_ids: list[str]) -> None:
    executor = ScopedToolExecutor(registry, now=lambda: "T")
    session = patient_ids[0]
    scope = ToolScope(allowed_tool_names=registry.all_tool_names, row_cap=2)
    result = executor.execute(
        [_call("get_labs", "call-7", patient_id=session, limit=100)],
        patient_id=session,
        scope=scope,
        run_id=RUN_ID,
    )
    assert result.evidence[0].args_after_scoping["limit"] == 2
    count = result.evidence[0].result["count"]
    assert isinstance(count, int)
    assert count <= 2


def test_row_cap_applies_when_model_sets_no_limit(
    registry: ToolRegistry, patient_ids: list[str]
) -> None:
    executor = ScopedToolExecutor(registry, now=lambda: "T")
    session = patient_ids[0]
    scope = ToolScope(allowed_tool_names=registry.all_tool_names, row_cap=3)
    result = executor.execute(
        [_call("get_labs", "call-8", patient_id=session)],
        patient_id=session,
        scope=scope,
        run_id=RUN_ID,
    )
    assert result.evidence[0].args_after_scoping["limit"] == 3


def test_forced_patient_id_applies_even_when_absent(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    # The model omits patient_id entirely; the executor still forces it.
    result = executor.execute(
        [_call("get_medications", "call-9")],
        patient_id=session,
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    assert not result.security_events
    assert result.evidence[0].args_after_scoping["patient_id"] == session


def test_batch_of_calls_is_each_addressable(
    executor: ScopedToolExecutor, registry: ToolRegistry, patient_ids: list[str]
) -> None:
    session = patient_ids[0]
    result = executor.execute(
        [
            _call("get_labs", "a", patient_id=session),
            _call("get_medications", "b", patient_id=session),
            _call("get_conditions", "c", patient_id=session),
        ],
        patient_id=session,
        scope=registry.full_scope(),
        run_id=RUN_ID,
    )
    ids = {record.tool_call_id for record in result.evidence}
    assert ids == {"a", "b", "c"}
    assert {message.tool_call_id for message in result.messages} == {"a", "b", "c"}
