"""Extracts the draft's claims for citation checking (docs/PLAN.md §5.3).

Runs on the `fast` profile — claim extraction is a mechanical decomposition, not
a reasoning task. The chain returns typed `ExtractedClaims` via
`with_structured_output` (§3.6). It re-derives the claims from the draft *body*
independently rather than trusting the draft's own claim list, so a draft cannot
mark an uncited assertion "cited" simply by omitting it from its claims — the
same narrow-projection argument the plan makes for pre-flight (§5.4).
"""

from __future__ import annotations

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from navigator.graph.protocols import ClaimExtractorChain
from navigator.prompts.loader import load_prompt
from navigator.schemas.postflight import ExtractedClaims


def build_claim_extractor_chain(model: BaseChatModel) -> ClaimExtractorChain:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("claim_extractor_v1")),
            (
                "human",
                "Draft answer:\n{draft_body}\n\n"
                "Recorded tool_call_ids you may cite:\n{tool_call_ids}\n\n"
                "Vetted education URLs you may cite:\n{education_urls}",
            ),
        ]
    )
    return cast(ClaimExtractorChain, prompt | model.with_structured_output(ExtractedClaims))
