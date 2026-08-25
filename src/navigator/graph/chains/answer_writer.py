"""Writes the cited PatientAnswer draft (docs/PLAN.md §5.1 `draft_answer`).

Runs on the `reasoning` profile — this is the model whose output the post-flight
scope judge grades. The chain returns a typed `PatientAnswer` via
`with_structured_output` (§3.6); the reading level is *measured* over the result
in `nodes/draft_answer.py`, not authored by the model (§8).
"""

from __future__ import annotations

from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from navigator.prompts.loader import load_prompt
from navigator.schemas.answer import PatientAnswer


class AnswerWriterChain(Protocol):
    def invoke(self, input: dict[str, object]) -> PatientAnswer: ...


def build_answer_writer_chain(model: BaseChatModel) -> AnswerWriterChain:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("answer_writer_v1")),
            (
                "human",
                "Question: {question}\n\n"
                "Reading-level target (Flesch-Kincaid grade): {reading_level_target}\n\n"
                "Evidence gathered (tool results and education pages):\n{evidence}",
            ),
        ]
    )
    return cast(AnswerWriterChain, prompt | model.with_structured_output(PatientAnswer))
