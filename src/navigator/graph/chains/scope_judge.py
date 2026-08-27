"""The post-flight scope judge (docs/PLAN.md §5.3).

Runs on the `reasoning` profile — this is the one place a model is asked to
grade the draft, and it is asked four narrow, falsifiable questions with a span
each, never a broad "is this safe?". A broad safety judgement from a model is
unmeasurable; four boolean-with-span questions are testable and each maps to a
specific boundary a clinical owner can point at. The chain returns a typed
`ScopeJudgement` via `with_structured_output` (§3.6).

`method="function_calling"`, not the default `json_schema` strict mode:
`ScopeJudgement.spans` is an open `dict[str, str]` (its keys are whichever of
the four boolean fields fired, not a fixed set), and OpenAI's strict
structured-output schema mode has no way to express an open-keyed object —
it requires every property to be named in advance. `function_calling` uses
OpenAI's tool-calling schema instead, which tolerates it. Found live: every
other chain's schema is closed (fixed fields, lists of fixed models) and
works under the strict default; this is the one open-dict field in the app.
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
    return cast(
        ScopeJudgeChain,
        prompt | model.with_structured_output(ScopeJudgement, method="function_calling"),
    )
