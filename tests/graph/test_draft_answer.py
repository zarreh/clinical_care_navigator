"""draft_answer produces a cited PatientAnswer with a measured reading level.

The answer writer is a stub chain (no LLM, no network); the reading level is
measured in code over the body, never authored by the model (§8).
"""

from __future__ import annotations

from typing import cast

from navigator.graph.nodes.draft_answer import READING_LEVEL_TARGET, build_draft_answer_node
from navigator.schemas.answer import Citation, Claim, PatientAnswer


class _StubAnswerWriter:
    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        return PatientAnswer(
            body="Your A1c is 7.8. That is above the range your lab reported.",
            claims=[
                Claim(
                    id="c1",
                    text="Your A1c is 7.8.",
                    kind="clinical",
                    evidence_refs=["call-1"],
                )
            ],
            citations=[Citation(claim_id="c1", tool_call_id="call-1")],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


def test_draft_answer_measures_reading_level() -> None:
    node = build_draft_answer_node(_StubAnswerWriter())
    state = {
        "question": "What does my A1c mean?",
        "literacy_level": "basic",
        "autonomy_level": "L2_balanced",
        "evidence": [],
    }
    result = node(state)  # type: ignore[arg-type]
    draft = result["draft"]
    assert isinstance(draft, PatientAnswer)
    # Target comes from the literacy band; measured is computed, not authored.
    assert draft.reading_level_target == READING_LEVEL_TARGET["basic"]
    assert draft.reading_level_measured is not None
    assert draft.autonomy_level == "L2_balanced"
    assert draft.claims[0].evidence_refs == ["call-1"]


def test_draft_answer_default_target_for_unknown_literacy() -> None:
    node = build_draft_answer_node(_StubAnswerWriter())
    state = {
        "question": "q",
        "literacy_level": "unknown-band",
        "autonomy_level": "L2_balanced",
        "evidence": [],
    }
    result = node(state)  # type: ignore[arg-type]
    assert (
        cast(PatientAnswer, result["draft"]).reading_level_target
        == READING_LEVEL_TARGET["intermediate"]
    )
