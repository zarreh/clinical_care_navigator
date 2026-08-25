"""Builds a TestClient over the *real* API surface wired to a stubbed, fully
offline navigator graph and fixture stores (docs/PLAN.md §5.8).

Every LLM-backed piece is injected, so the whole conversation and review-resume
path runs with no network and no key. Dependency overrides swap the real graph,
run store, review queue and record store for the fixtures, so the background task
and the resume handler use the same instances the assertions inspect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall
from langgraph.checkpoint.memory import MemorySaver

from navigator.api import deps
from navigator.api.main import app
from navigator.graph.builder import NavigatorGraph, build_navigator_graph
from navigator.schemas.answer import Citation, Claim, PatientAnswer
from navigator.schemas.postflight import ExtractedClaims, ScopeJudgement
from navigator.schemas.preflight import IntentAssessment
from navigator.settings import Settings
from navigator.store import RecordStore, ReviewQueue, RunStore
from tests.fixtures import build_fixture_stores

_HBA1C = "4548-4"


class _StubIntent:
    def invoke(self, _input: dict[str, str]) -> IntentAssessment:
        return IntentAssessment(
            question_class="lab_education", red_flags=[], confidence=0.9, rationale_span="result"
        )


class _OneToolExplainer:
    def __init__(self, patient_id: str, loinc: str) -> None:
        self._patient_id = patient_id
        self._loinc = loinc
        self._called = False

    def invoke(self, _messages: object) -> AIMessage:
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

    def invoke(self, _input: dict[str, object]) -> PatientAnswer:
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

    def invoke(self, _input: dict[str, object]) -> ExtractedClaims:
        return ExtractedClaims(claims=self._claims)


class _FixedScopeJudge:
    def __init__(self, **flags: object) -> None:
        self._judgement = ScopeJudgement(**flags)  # type: ignore[arg-type]

    def invoke(self, _input: dict[str, object]) -> ScopeJudgement:
        return self._judgement


@dataclass
class NavigatorTestContext:
    client: TestClient
    run_store: RunStore
    review_queue: ReviewQueue
    record_store: RecordStore
    graph: NavigatorGraph
    settings: Settings
    patient_id: str
    draft_body: str


def build_navigator_test_context(
    tmp_path: Path, *, scope_violation: bool, draft_body: str = "Your result is recorded."
) -> NavigatorTestContext:
    stores = build_fixture_stores(tmp_path)
    run_db = tmp_path / "runs.db"
    checkpoint_db = tmp_path / "checkpoints.db"
    settings = Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
        run_store_path=str(run_db),
        checkpoint_db_path=str(checkpoint_db),
    )
    patient_id = stores.patient_ids[0]
    claim = Claim(
        id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=["call-1"]
    )
    judge_flags: dict[str, object] = (
        {"directs_clinical_action": True, "spans": {"directs_clinical_action": "schedule an MRI"}}
        if scope_violation
        else {}
    )
    # MemorySaver is async-capable and in-process: the create request and the
    # later decision request share this one graph singleton, so the review
    # resumes from the same checkpoint (docs/PLAN.md §5.10).
    graph = build_navigator_graph(
        settings,
        intent_chain=_StubIntent(),
        explainer=_OneToolExplainer(patient_id, _HBA1C),
        answer_writer_chain=_FixedAnswerWriter(draft_body, [claim]),
        claim_extractor_chain=_FixedClaimExtractor([claim]),
        scope_judge_chain=_FixedScopeJudge(**judge_flags),
        checkpointer=MemorySaver(),
    )
    run_store = RunStore(run_db)
    review_queue = ReviewQueue(run_db)
    record_store = RecordStore(stores.records_db)

    app.dependency_overrides[deps.get_navigator_graph] = lambda: graph
    app.dependency_overrides[deps.get_run_store] = lambda: run_store
    app.dependency_overrides[deps.get_review_queue] = lambda: review_queue
    app.dependency_overrides[deps.get_record_store] = lambda: record_store
    app.dependency_overrides[deps.settings_dependency] = lambda: settings

    return NavigatorTestContext(
        client=TestClient(app),
        run_store=run_store,
        review_queue=review_queue,
        record_store=record_store,
        graph=graph,
        settings=settings,
        patient_id=patient_id,
        draft_body=draft_body,
    )


def reset_navigator_overrides() -> None:
    app.dependency_overrides.clear()
