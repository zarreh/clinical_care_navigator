"""The contextualizer: turns a follow-up into a standalone question.

Runs only when the conversation has earlier turns. Its output is a rewritten
question that the rest of the pipeline treats exactly like any other question, so
pre-flight screening, scoped tools and post-flight checks all apply to it unchanged.
The patient's own words are kept alongside it (see `nodes/contextualize.py`) and are
screened too, so a rewrite cannot hide a red flag.
"""

from __future__ import annotations

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from navigator.graph.protocols import ContextualizerChain
from navigator.prompts.loader import load_prompt
from navigator.schemas.preflight import StandaloneQuestion


def build_contextualizer_chain(model: BaseChatModel) -> ContextualizerChain:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("contextualize_v1")),
            ("human", "Earlier turns:\n{history}\n\nNew message:\n{question}"),
        ]
    )
    return cast(
        ContextualizerChain,
        prompt | model.with_structured_output(StandaloneQuestion),
    )
