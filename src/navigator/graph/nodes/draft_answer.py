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


def build_draft_answer_node(
    answer_writer_chain: AnswerWriterChain,
) -> Callable[[NavigatorState], dict[str, object]]:
    def draft_answer_node(state: NavigatorState) -> dict[str, object]:
        target = READING_LEVEL_TARGET.get(state.get("literacy_level", ""), _DEFAULT_TARGET)
        evidence = [record.model_dump(mode="json") for record in state.get("evidence", [])]
        draft = answer_writer_chain.invoke(
            {
                "question": state["question"],
                "reading_level_target": target,
                "evidence": evidence,
            }
        )
        measured = float(textstat.flesch_kincaid_grade(draft.body))
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
