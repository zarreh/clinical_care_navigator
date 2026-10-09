"""Writes the cited PatientAnswer draft (docs/PLAN.md §5.1 `draft_answer`).

The answer writer chain produces the body, claims and citations from the
gathered evidence. The reading level is then **measured** over the body in code
— never authored by the model — so the equity claim is a measurement, not an
assertion (§8). The target comes from the patient's literacy level and is shown
in the UI: adapting to a person *with* them, not silently (§3.7).
"""

from __future__ import annotations

from collections.abc import Callable

import textstat

from navigator.graph.chains.answer_writer import AnswerWriterChain
from navigator.graph.state import NavigatorState
from navigator.schemas.answer import PatientAnswer

# Stated reading-level targets (Flesch-Kincaid grade) per literacy band. Shown
# in the UI; the measured level is compared against them in the eval harness.
READING_LEVEL_TARGET = {
    "basic": 6.0,
    "intermediate": 8.0,
    "proficient": 10.0,
}
_DEFAULT_TARGET = READING_LEVEL_TARGET["intermediate"]


def _grade(body: str) -> float:
    return float(textstat.flesch_kincaid_grade(body))


def build_draft_answer_node(
    answer_writer_chain: AnswerWriterChain,
) -> Callable[[NavigatorState], dict[str, object]]:
    def draft_answer_node(state: NavigatorState) -> dict[str, object]:
        target = READING_LEVEL_TARGET.get(state.get("literacy_level", ""), _DEFAULT_TARGET)
        evidence = [record.model_dump(mode="json") for record in state.get("evidence", [])]
        request: dict[str, object] = {
            "question": state["question"],
            "reading_level_target": target,
            "evidence": evidence,
            "revision_feedback": "",
        }
        draft = answer_writer_chain.invoke(request)
        measured = _grade(draft.body)
        if measured > target:
            # One rewrite, told its measured grade: a model given only a target number
            # misses it most of the time. Keep whichever draft reads easier, never a worse one.
            revised = answer_writer_chain.invoke(
                {
                    **request,
                    "revision_feedback": (
                        f"Your previous answer reads at grade {measured:.1f}; the target is "
                        f"{target:.1f}. Rewrite the body with shorter sentences and everyday "
                        "words. Keep every claim and citation exactly as they are."
                    ),
                }
            )
            revised_measured = _grade(revised.body)
            if revised_measured < measured:
                draft, measured = revised, revised_measured
        # Rebuild frozen model with the measured level and the run's metadata.
        answer = PatientAnswer(
            **{
                k: v
                for k, v in draft.model_dump().items()
                if k not in {"reading_level_target", "reading_level_measured", "autonomy_level"}
            },
            reading_level_target=target,
            reading_level_measured=measured,
            autonomy_level=state.get("autonomy_level", "L2_balanced"),
        )
        return {"draft": answer}

    return draft_answer_node
