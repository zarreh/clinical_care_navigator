"""End-to-end: a question in, a cited PatientAnswer draft out (Phase 4 exit).

The graph is assembled with stub LLM-backed pieces — a stub intent classifier, a
stub explainer that makes one real tool call through the scoped executor, and a
stub answer writer — over the offline fixture stores. No LLM, no network. This
proves the wiring: intake → pre-flight gate → investigate (scoped tools) →
draft_answer → a PatientAnswer whose citations resolve to recorded evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall

from navigator.graph.builder import build_navigator_graph
from navigator.schemas.answer import Citation, Claim, PatientAnswer
from navigator.schemas.postflight import ExtractedClaims, ScopeJudgement
from navigator.schemas.preflight import IntentAssessment
from navigator.settings import Settings
from tests.fixtures import build_fixture_stores


class _StubIntent:
    def invoke(self, input: dict[str, str]) -> IntentAssessment:
        return IntentAssessment(
            question_class="lab_education", red_flags=[], confidence=0.9, rationale_span="A1c"
        )


class _StubExplainer:
    """Makes one real get_labs call, then stops."""

    def __init__(self, patient_id: str) -> None:
        self._patient_id = patient_id
        self._called = False

    def invoke(self, messages):  # type: ignore[no-untyped-def]
        if not self._called:
            self._called = True
            return AIMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        name="get_labs",
                        args={"patient_id": self._patient_id, "loinc_code": "18262-6"},
                        id="call-1",
                        type="tool_call",
                    )
                ],
            )
        return AIMessage(content="I have the labs.")


class _StubAnswerWriter:
    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        return PatientAnswer(
            body="Your LDL cholesterol result is recorded in your chart.",
            claims=[
                Claim(
                    id="c1",
                    text="Your LDL cholesterol result is recorded.",
                    kind="clinical",
                    evidence_refs=["call-1"],
                )
            ],
            citations=[Citation(claim_id="c1", tool_call_id="call-1")],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


class _StubClaimExtractor:
    """Re-derives the draft's single clinical claim, citing the recorded call."""

    def invoke(self, input: dict[str, object]) -> ExtractedClaims:
        return ExtractedClaims(
            claims=[
                Claim(
                    id="c1",
                    text="Your LDL cholesterol result is recorded.",
                    kind="clinical",
                    evidence_refs=["call-1"],
                )
            ]
        )


class _StubScopeJudge:
    """A clean draft: no boundary crossed."""

    def invoke(self, input: dict[str, object]) -> ScopeJudgement:
        return ScopeJudgement()


@pytest.fixture
def graph_and_patient(tmp_path: Path) -> tuple[object, str]:
    stores = build_fixture_stores(tmp_path)
    settings = Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
    )
    patient_id = stores.patient_ids[0]
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        answer_writer_chain=_StubAnswerWriter(),
        explainer=_StubExplainer(patient_id),
        claim_extractor_chain=_StubClaimExtractor(),
        scope_judge_chain=_StubScopeJudge(),
    )
    return graph, patient_id


def test_question_to_cited_patient_answer(graph_and_patient) -> None:  # type: ignore[no-untyped-def]
    graph, patient_id = graph_and_patient
    final = graph.invoke(
        {
            "question": "What does my LDL cholesterol mean?",
            "patient_id": patient_id,
            "run_id": "run-e2e",
        }
    )
    draft = final["draft"]
    assert isinstance(draft, PatientAnswer)
    # The pre-flight gate allowed the question and the run reached draft_answer.
    assert final["policy_decision"].action == "allow"
    # Citations resolve to a recorded tool_call_id in the run's evidence.
    evidence_ids = {record.tool_call_id for record in final["evidence"]}
    assert "call-1" in evidence_ids
    assert draft.citations[0].tool_call_id in evidence_ids
    # Reading level was measured, not authored.
    assert draft.reading_level_measured is not None
    # Post-flight cleared the draft and published it byte-identically (§5.3).
    assert final["post_flight"].disposition == "publish"
    assert final["published"].body == draft.body
    assert final["published"].disposition == "answered"


def test_emergency_question_short_circuits_before_tools(graph_and_patient) -> None:  # type: ignore[no-untyped-def]
    graph, patient_id = graph_and_patient
    final = graph.invoke(
        {
            "question": "Crushing chest pain, my left arm is numb",
            "patient_id": patient_id,
            "run_id": "run-emergency",
        }
    )
    # direct_to_emergency_care: templated, and zero patient tool calls (§3.3).
    assert final["policy_decision"].action == "direct_to_emergency_care"
    assert final["draft"].disposition == "templated"
    assert final.get("tool_call_count", 0) == 0
    assert final.get("evidence", []) == []
