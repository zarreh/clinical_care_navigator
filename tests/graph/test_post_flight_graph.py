"""Full-graph post-flight acceptance behaviours (Phase 5 exit criteria, §5.3).

Assembled with stub LLM pieces over the offline fixture stores — no LLM, no
network. These prove the four behaviours end to end through the real wiring:

- (a) a benign question over a critical value escalates;
- (b) an uncited draft loops back once with feedback and gains the citation;
- (c) the scope judge blocks a diagnosing draft with a span;
- (e) post-flight escalates but the published/held answer is never less
      restrictive than the pre-flight decision.

The enqueue_review interrupt (§5.10) is exercised with a MemorySaver.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from navigator.graph.builder import build_navigator_graph
from navigator.schemas.answer import Citation, Claim, PatientAnswer
from navigator.schemas.postflight import ExtractedClaims, ScopeJudgement
from navigator.schemas.preflight import IntentAssessment
from navigator.settings import Settings
from tests.fixtures import build_fixture_stores

_POTASSIUM = "2823-3"


def _critical_patient(records_db: Path) -> str:
    """The patient carrying case 4's injected critical potassium (scenario_fixtures)."""
    con = sqlite3.connect(records_db)
    try:
        row = con.execute(
            "SELECT patient_id FROM observations "
            "WHERE loinc_code = ? AND value_number >= 6.0 LIMIT 1",
            (_POTASSIUM,),
        ).fetchone()
    finally:
        con.close()
    assert row is not None, "fixture must contain the injected critical potassium"
    return str(row[0])


class _StubIntent:
    def invoke(self, input: dict[str, str]) -> IntentAssessment:
        return IntentAssessment(
            question_class="lab_education", red_flags=[], confidence=0.9, rationale_span="potassium"
        )


class _OneToolExplainer:
    """Makes one get_labs call for the given loinc, then stops."""

    def __init__(self, patient_id: str, loinc: str) -> None:
        self._patient_id = patient_id
        self._loinc = loinc
        self._called = False

    def invoke(self, messages):  # type: ignore[no-untyped-def]
        if not self._called:
            self._called = True
            return AIMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        name="get_labs",
                        args={"patient_id": self._patient_id, "loinc_code": self._loinc},
                        id="call-1",
                        type="tool_call",
                    )
                ],
            )
        return AIMessage(content="done")


class _FixedAnswerWriter:
    def __init__(self, body: str, claims: list[Claim]) -> None:
        self._body = body
        self._claims = claims

    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        return PatientAnswer(
            body=self._body,
            claims=self._claims,
            citations=[
                Citation(claim_id=c.id, tool_call_id=c.evidence_refs[0])
                for c in self._claims
                if c.evidence_refs
            ],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


class _FixedClaimExtractor:
    def __init__(self, claims: list[Claim]) -> None:
        self._claims = claims

    def invoke(self, input: dict[str, object]) -> ExtractedClaims:
        return ExtractedClaims(claims=self._claims)


class _FixedScopeJudge:
    def __init__(self, **flags: object) -> None:
        self._judgement = ScopeJudgement(**flags)  # type: ignore[arg-type]

    def invoke(self, input: dict[str, object]) -> ScopeJudgement:
        return self._judgement


def _settings(tmp_path: Path) -> tuple[Settings, str, Path]:
    stores = build_fixture_stores(tmp_path)
    settings = Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
    )
    return settings, _critical_patient(stores.records_db), stores.records_db


# --- (a) critical value escalates a benign question --------------------------


def test_benign_question_over_critical_value_escalates(tmp_path: Path) -> None:
    settings, patient_id, _ = _settings(tmp_path)
    claim = Claim(
        id="c1",
        text="Your potassium result is recorded.",
        kind="clinical",
        evidence_refs=["call-1"],
    )
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        explainer=_OneToolExplainer(patient_id, _POTASSIUM),
        answer_writer_chain=_FixedAnswerWriter("Your potassium result is recorded.", [claim]),
        claim_extractor_chain=_FixedClaimExtractor([claim]),
        scope_judge_chain=_FixedScopeJudge(),
    )
    final = graph.invoke(
        {
            "question": "What does my potassium result mean?",
            "patient_id": patient_id,
            "run_id": "run-case4",
        }
    )
    # Pre-flight allowed the benign question, but post-flight escalated on the value.
    assert final["policy_decision"].action == "allow"
    assert final["post_flight"].trigger == "critical_value"
    assert final["post_flight"].override_action == "direct_to_emergency_care"
    # The escalation was rendered as a templated emergency response, and it cites
    # the published threshold rather than asserting a bare number.
    published = final["published"]
    assert published.disposition == "templated"
    assert "emergency care" in published.body
    assert "6.0" in published.body


# --- (c) scope judge blocks a diagnosing draft with a span -------------------


def test_scope_judge_blocks_diagnosing_draft(tmp_path: Path) -> None:
    settings, patient_id, _ = _settings(tmp_path)
    # Use a patient/loinc with no critical value so check 1 doesn't pre-empt.
    claim = Claim(
        id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=["call-1"]
    )
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        explainer=_OneToolExplainer(patient_id, "4548-4"),  # HbA1c, no critical band
        answer_writer_chain=_FixedAnswerWriter("Based on this, you have diabetes.", [claim]),
        claim_extractor_chain=_FixedClaimExtractor([claim]),
        scope_judge_chain=_FixedScopeJudge(
            diagnoses=True, spans={"diagnoses": "you have diabetes"}
        ),
    )
    final = graph.invoke(
        {
            "question": "What does my A1c mean?",
            "patient_id": patient_id,
            "run_id": "run-scope",
        }
    )
    assert final["post_flight"].trigger == "scope_judge"
    assert final["post_flight"].override_action == "out_of_scope"
    published = final["published"]
    assert published.disposition == "templated"
    # The routing shows its basis: the draft's own diagnosing span.
    assert "you have diabetes" in published.body


# --- (b) uncited draft loops back once and gains the citation ----------------


class _TwoPassAnswerWriter:
    """Uncited on the first pass, cited on the second (after the loop feedback)."""

    def __init__(self) -> None:
        self._calls = 0

    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        self._calls += 1
        if self._calls == 1:
            claims = [
                Claim(id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=[])
            ]
        else:
            claims = [
                Claim(
                    id="c1",
                    text="Your result is recorded.",
                    kind="clinical",
                    evidence_refs=["call-1"],
                )
            ]
        return PatientAnswer(
            body="Your result is recorded.",
            claims=claims,
            citations=[
                Citation(claim_id=c.id, tool_call_id=c.evidence_refs[0])
                for c in claims
                if c.evidence_refs
            ],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


class _TwoPassClaimExtractor:
    def __init__(self) -> None:
        self._calls = 0

    def invoke(self, input: dict[str, object]) -> ExtractedClaims:
        self._calls += 1
        refs = [] if self._calls == 1 else ["call-1"]
        return ExtractedClaims(
            claims=[
                Claim(id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=refs)
            ]
        )


def test_uncited_draft_loops_back_and_gains_citation(tmp_path: Path) -> None:
    settings, patient_id, _ = _settings(tmp_path)
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        explainer=_OneToolExplainer(patient_id, "4548-4"),  # HbA1c, no critical band
        answer_writer_chain=_TwoPassAnswerWriter(),
        claim_extractor_chain=_TwoPassClaimExtractor(),
        scope_judge_chain=_FixedScopeJudge(),
    )
    final = graph.invoke(
        {
            "question": "What does my A1c mean?",
            "patient_id": patient_id,
            "run_id": "run-loop",
        }
    )
    # The loop ran exactly once (evidence_pass reached 1) and then published.
    assert final["evidence_pass"] == 1
    assert final["post_flight"].disposition == "publish"
    assert final["post_flight"].citation_coverage == 1.0
    assert final["published"].body == final["draft"].body


# --- (§5.10) enqueue_review genuinely suspends with a checkpointer -----------


def test_enqueue_review_interrupts_with_checkpointer(tmp_path: Path) -> None:
    settings, patient_id, _ = _settings(tmp_path)
    claim = Claim(
        id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=["call-1"]
    )
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        explainer=_OneToolExplainer(patient_id, "4548-4"),
        answer_writer_chain=_FixedAnswerWriter("You should schedule an MRI.", [claim]),
        claim_extractor_chain=_FixedClaimExtractor([claim]),
        scope_judge_chain=_FixedScopeJudge(
            directs_clinical_action=True, spans={"directs_clinical_action": "schedule an MRI"}
        ),
        checkpointer=MemorySaver(),
    )
    config: RunnableConfig = {"configurable": {"thread_id": "t-review"}}
    final = graph.invoke(
        {
            "question": "What does my A1c mean?",
            "patient_id": patient_id,
            "run_id": "run-review",
        },
        config,
    )
    # The run suspended at enqueue_review rather than publishing.
    assert "__interrupt__" in final
    assert "published" not in final
    # The post-flight decision that drove the hold was a review, more restrictive
    # than the pre-flight allow.
    state = graph.get_state(config)
    assert state.values["post_flight"].disposition == "review"
    assert state.values["post_flight"].override_action == "clinician_review"
