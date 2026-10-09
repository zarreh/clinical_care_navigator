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


_HARD = (
    "Glycated haemoglobin concentration measurements quantify cumulative glycaemic exposure "
    "across approximately three months, therefore interpretation necessitates professional "
    "consultation."
)
_MID = (
    "Glycated haemoglobin measurements quantify cumulative glycaemic exposure across "
    "approximately three months, so ask your clinician."
)
_EASY = "Your A1c is 7.8. It shows your blood sugar over a few months. Talk to your care team."


class _ScriptedWriter:
    """Returns one body per call and records what it was asked."""

    def __init__(self, *bodies: str) -> None:
        self._bodies = list(bodies)
        self.inputs: list[dict[str, object]] = []

    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        self.inputs.append(input)
        body = self._bodies[min(len(self.inputs), len(self._bodies)) - 1]
        return PatientAnswer(
            body=body,
            claims=[Claim(id="c1", text="Your A1c is 7.8.", kind="clinical", evidence_refs=["x"])],
            citations=[Citation(claim_id="c1", tool_call_id="x")],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


def _run(writer: _ScriptedWriter, literacy: str = "basic") -> PatientAnswer:
    node = build_draft_answer_node(writer)
    state = {"question": "q", "literacy_level": literacy, "autonomy_level": "L2_balanced"}
    return cast(PatientAnswer, node(state)["draft"])  # type: ignore[arg-type]


def test_a_draft_over_target_is_rewritten_once_with_its_measured_grade() -> None:
    writer = _ScriptedWriter(_HARD, _EASY)

    draft = _run(writer)

    assert len(writer.inputs) == 2
    assert draft.body == _EASY
    assert draft.reading_level_measured is not None
    assert draft.reading_level_measured <= READING_LEVEL_TARGET["basic"]
    feedback = str(writer.inputs[1]["revision_feedback"])
    assert "26.4" in feedback
    assert "6.0" in feedback


def test_a_draft_already_at_target_is_not_rewritten() -> None:
    writer = _ScriptedWriter(_EASY)

    _run(writer)

    assert len(writer.inputs) == 1
    assert writer.inputs[0]["revision_feedback"] == ""


def test_the_rewrite_is_attempted_once_and_a_worse_draft_is_not_kept() -> None:
    writer = _ScriptedWriter(_MID, _HARD, _EASY)

    draft = _run(writer)

    assert len(writer.inputs) == 2
    assert draft.body == _MID
