"""Graph state.

`SkeletonState` is the Phase 0 walking skeleton, kept so the streaming path
stays proven end to end. `NavigatorState` is the real state (docs/PLAN.md §5.1),
carrying the pre-flight decision, the scoped-executor output, and the draft.

The narrow per-node projections (§5.4) are enforced by what each node reads,
not by separate TypedDicts: `classify_intent` reads only the question and the
patient's literacy level — never clinical content — which is a deliberate,
defensible privacy property stated in the docs.
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import BaseMessage

from navigator.schemas.answer import PatientAnswer
from navigator.schemas.preflight import IntentAssessment, PolicyDecision, RuleMatch
from navigator.schemas.scoping import EvidenceRecord, SecurityEvent


class SkeletonState(TypedDict):
    """Walking-skeleton state — replaced by `NavigatorState` in the real graph."""

    question: str
    steps: list[str]


class NavigatorState(TypedDict, total=False):
    """The real graph state (§5.1).

    `total=False` because the state accumulates: intake sets the patient header,
    the pre-flight gate sets the decision, investigate appends evidence, and
    draft_answer sets the draft. Keys are present only after the node that owns
    them has run.
    """

    # intake
    question: str
    patient_id: str
    run_id: str
    literacy_level: str
    language: str
    autonomy_level: str
    started_at: float

    # pre-flight gate
    rule_matches: list[RuleMatch]
    intent: IntentAssessment
    policy_decision: PolicyDecision

    # investigate (the scoped executor's output)
    messages: list[BaseMessage]
    evidence: list[EvidenceRecord]
    security_events: list[SecurityEvent]
    tool_call_count: int

    # draft
    draft: PatientAnswer
