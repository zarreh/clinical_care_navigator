"""The intent classifier — the pre-flight gate's single LLM call (§5.2 layer 2).

Runs in parallel with the deterministic `screen_rules`, not after it, so exactly
one model call happens before any evidence is gathered. It catches what the
keyword screen cannot: metaphor (canonical case 11, "like an elephant sitting on
my chest"), paraphrase, and the intent behind indirect phrasing. It returns an
`IntentAssessment` via `with_structured_output`, never free text (§3.6).

The chain is a pure LCEL runnable; combining its output with the rule screen by
severity precedence is `nodes/resolve_policy.py`'s job, not this chain's.
"""

from __future__ import annotations

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from navigator.graph.protocols import IntentClassifierChain
from navigator.prompts.loader import load_prompt
from navigator.schemas.preflight import IntentAssessment


def build_intent_classifier_chain(model: BaseChatModel) -> IntentClassifierChain:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("intent_classifier_v1")),
            ("human", "{question}"),
        ]
    )
    return cast(
        IntentClassifierChain,
        prompt | model.with_structured_output(IntentAssessment),
    )
