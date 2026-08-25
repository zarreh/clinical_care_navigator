"""The post-flight scope judge (docs/PLAN.md §5.3).

Runs on the `reasoning` profile — this is the one place a model is asked to
grade the draft, and it is asked four narrow, falsifiable questions with a span
each, never a broad "is this safe?". A broad safety judgement from a model is
unmeasurable; four boolean-with-span questions are testable and each maps to a
specific boundary a clinical owner can point at. The chain returns a typed
`ScopeJudgement` via `with_structured_output` (§3.6).
"""

from __future__ import annotations

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from navigator.graph.protocols import ScopeJudgeChain
from navigator.prompts.loader import load_prompt
from navigator.schemas.postflight import ScopeJudgement


def build_scope_judge_chain(model: BaseChatModel) -> ScopeJudgeChain:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("scope_judge_v1")),
            ("human", "Draft answer:\n{draft_body}"),
        ]
    )
    return cast(ScopeJudgeChain, prompt | model.with_structured_output(ScopeJudgement))
