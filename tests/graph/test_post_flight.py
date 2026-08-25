"""Post-flight orchestration — the centrepiece (§5.3).

Exercises the node's three checks and the monotonic override, each with a fake
scope-judge and the fixture store's real reference-range lookup. The three
acceptance behaviours from the Phase 5 exit criteria live here: case 4 escalates,
an uncited draft loops back once, and a diagnosing draft is blocked with a span.
"""

from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage

from navigator.graph.nodes.post_flight import build_post_flight_node
from navigator.graph.state import NavigatorState
from navigator.schemas.answer import Citation, Claim, PatientAnswer
from navigator.schemas.postflight import PostFlightResult, ScopeJudgement
from navigator.schemas.preflight import PolicyDecision, more_restrictive
from navigator.schemas.scoping import EvidenceRecord, ToolScope
from navigator.store.record_store import RecordStore

_POTASSIUM = "2823-3"


def _pf(out: dict[str, object]) -> PostFlightResult:
    return cast(PostFlightResult, out["post_flight"])


class _ScopeJudge:
    def __init__(self, **flags: object) -> None:
        self._judgement = ScopeJudgement(**flags)  # type: ignore[arg-type]

    def invoke(self, input: dict[str, object]) -> ScopeJudgement:
        return self._judgement


def _allow_decision() -> PolicyDecision:
    return PolicyDecision(
        action="allow",
        band="inform",
        rule_matches=[],
        layer_agreement=True,
        tool_scope=ToolScope(allowed_tool_names=frozenset(), row_cap=25),
        autonomy_level="L2_balanced",
    )


def _draft(body: str, claims: list[Claim]) -> PatientAnswer:
    return PatientAnswer(
        body=body,
        claims=claims,
        citations=[
            Citation(claim_id=c.id, tool_call_id=c.evidence_refs[0])
            for c in claims
            if c.evidence_refs
        ],
        reading_level_target=8.0,
        reading_level_measured=7.0,
        autonomy_level="L2_balanced",
    )


def _labs_evidence(value: float, *, call_id: str = "call-1") -> EvidenceRecord:
    return EvidenceRecord(
        tool_call_id=call_id,
        tool_name="get_labs",
        args_after_scoping={},
        result={"labs": [{"loinc_code": _POTASSIUM, "value_number": value, "units": "mmol/L"}]},
        retrieved_at="2026-08-20T00:00:00+00:00",
    )


def _state(draft: PatientAnswer, evidence: list[EvidenceRecord], **extra: object) -> NavigatorState:
    state: NavigatorState = {
        "draft": draft,
        "evidence": evidence,
        "claims": list(draft.claims),
        "policy_decision": _allow_decision(),
        "messages": [],
    }
    state.update(extra)  # type: ignore[typeddict-item]
    return state


# --- check 1: critical value escalates (case 4) ------------------------------


def test_critical_value_escalates(record_store: RecordStore) -> None:
    claim = Claim(
        id="c1",
        text="Your potassium result is recorded.",
        kind="clinical",
        evidence_refs=["call-1"],
    )
    node = build_post_flight_node(
        record_store.reference_range, _ScopeJudge(), floor=1.0, max_evidence_passes=1
    )
    out = node(_state(_draft("Your potassium result is 6.9.", [claim]), [_labs_evidence(6.9)]))
    result = _pf(out)
    assert result.disposition == "escalate"
    assert result.trigger == "critical_value"
    assert result.override_action == "direct_to_emergency_care"
    assert result.critical_findings[0].analyte == "Potassium"


def test_critical_value_beats_a_clean_scope_judge(record_store: RecordStore) -> None:
    # Even with a perfectly clean draft, the value itself forces escalation.
    claim = Claim(id="c1", text="recorded", kind="clinical", evidence_refs=["call-1"])
    node = build_post_flight_node(
        record_store.reference_range, _ScopeJudge(diagnoses=False), floor=1.0, max_evidence_passes=1
    )
    out = node(_state(_draft("A calm, cited answer.", [claim]), [_labs_evidence(6.9)]))
    assert _pf(out).trigger == "critical_value"


# --- check 2: citation coverage loops once, then reviews ---------------------


def test_uncited_claim_loops_back_once(record_store: RecordStore) -> None:
    uncited = Claim(id="c1", text="You should take 40mg.", kind="clinical", evidence_refs=[])
    node = build_post_flight_node(
        record_store.reference_range, _ScopeJudge(), floor=1.0, max_evidence_passes=1
    )
    out = node(_state(_draft("You should take 40mg.", [uncited]), [_labs_evidence(4.5)]))
    result = _pf(out)
    assert result.disposition == "loop"
    assert result.trigger == "citation_coverage"
    assert result.uncited_claim_ids == ["c1"]
    assert out["evidence_pass"] == 1
    # The loop appends specific feedback for the next pass.
    feedback = cast(list[object], out["messages"])[-1]
    assert isinstance(feedback, HumanMessage)
    assert "c1" in feedback.content


def test_still_uncited_after_retry_routes_to_review(record_store: RecordStore) -> None:
    uncited = Claim(id="c1", text="You should take 40mg.", kind="clinical", evidence_refs=[])
    node = build_post_flight_node(
        record_store.reference_range, _ScopeJudge(), floor=1.0, max_evidence_passes=1
    )
    # evidence_pass already at the max: no further loop, hold for review.
    out = node(
        _state(_draft("You should take 40mg.", [uncited]), [_labs_evidence(4.5)], evidence_pass=1)
    )
    result = _pf(out)
    assert result.disposition == "review"
    assert result.override_action == "clinician_review"


# --- check 3: scope judge blocks a diagnosing draft with a span --------------


def test_scope_judge_blocks_diagnosis_with_span(record_store: RecordStore) -> None:
    claim = Claim(id="c1", text="recorded", kind="clinical", evidence_refs=["call-1"])
    judge = _ScopeJudge(diagnoses=True, spans={"diagnoses": "you have hyperkalemia"})
    node = build_post_flight_node(
        record_store.reference_range, judge, floor=1.0, max_evidence_passes=1
    )
    out = node(
        _state(_draft("Based on this, you have hyperkalemia.", [claim]), [_labs_evidence(4.5)])
    )
    result = _pf(out)
    assert result.disposition == "escalate"
    assert result.trigger == "scope_judge"
    assert result.override_action == "out_of_scope"
    assert result.scope_judgement is not None
    assert result.scope_judgement.spans["diagnoses"] == "you have hyperkalemia"


def test_scope_judge_directs_action_routes_to_review(record_store: RecordStore) -> None:
    claim = Claim(id="c1", text="recorded", kind="clinical", evidence_refs=["call-1"])
    judge = _ScopeJudge(
        directs_clinical_action=True, spans={"directs_clinical_action": "order an MRI"}
    )
    node = build_post_flight_node(
        record_store.reference_range, judge, floor=1.0, max_evidence_passes=1
    )
    out = node(_state(_draft("You should order an MRI.", [claim]), [_labs_evidence(4.5)]))
    result = _pf(out)
    assert result.disposition == "review"
    assert result.override_action == "clinician_review"


# --- clean publish -----------------------------------------------------------


def test_clean_draft_publishes(record_store: RecordStore) -> None:
    claim = Claim(
        id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=["call-1"]
    )
    node = build_post_flight_node(
        record_store.reference_range, _ScopeJudge(), floor=1.0, max_evidence_passes=1
    )
    out = node(_state(_draft("Your result is recorded.", [claim]), [_labs_evidence(4.5)]))
    result = _pf(out)
    assert result.disposition == "publish"
    assert result.trigger == "none"
    assert result.citation_coverage == 1.0


# --- the monotonic property (post-flight never relaxes pre-flight) -----------


def test_more_restrictive_never_relaxes() -> None:
    # A pre-flight clinician_review combined with an allow-level override stays
    # clinician_review — post-flight cannot lower the pre-flight floor.
    assert more_restrictive("clinician_review", "allow") == "clinician_review"
    # And it can raise it.
    assert more_restrictive("allow", "direct_to_emergency_care") == "direct_to_emergency_care"
    # Emergency dominates everything.
    for other in ("allow", "clinician_review", "out_of_scope", "crisis"):
        assert more_restrictive("direct_to_emergency_care", other) == "direct_to_emergency_care"
