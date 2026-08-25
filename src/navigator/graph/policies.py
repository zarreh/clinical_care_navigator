"""Model selection per node — never inline in a node (docs/PLAN.md §5.4).

Two profiles, carried from A2: a cheap `fast` model for high-volume reasoning
(the investigator, the intent classifier) and a stronger `reasoning` model for
the judgements the answer is graded on (the answer writer, the post-flight scope
judge). Fallback belongs here and is engaged only on transport-level failure,
never to paper over a schema or tool-calling defect.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from navigator.settings import Settings

FAST_MODEL = "gpt-4o-mini"
REASONING_MODEL = "gpt-4o"


def _api_key(settings: Settings) -> SecretStr | None:
    return SecretStr(settings.openai_api_key) if settings.openai_api_key else None


def build_fast_model(settings: Settings) -> ChatOpenAI:
    """Intent classifier, investigator — cheap, high-volume reasoning."""
    return ChatOpenAI(model=FAST_MODEL, temperature=0, api_key=_api_key(settings))


def build_reasoning_model(settings: Settings) -> ChatOpenAI:
    """Answer writer, scope judge — the models whose output is graded."""
    return ChatOpenAI(model=REASONING_MODEL, temperature=0, api_key=_api_key(settings))
