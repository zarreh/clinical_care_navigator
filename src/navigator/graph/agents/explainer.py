"""A model + a scoped tool set + a prompt id, nothing else (docs/PLAN.md §9.3).

The explainer is the agent that answers a patient's question about their own
record. It is bound to the tools the pre-flight gate's `ToolScope` permits — for
an `allow` decision that is the full registry; the tools are executed by the
scoped executor in `nodes/investigate.py`, never by a raw ToolNode, so patient
scoping and the row cap are enforced on every call (§3.4).

The system prompt is injected once by `nodes/investigate.py` when the loop
begins; this module just binds the tools to the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import StructuredTool


class Explainer(Protocol):
    def invoke(self, messages: Sequence[BaseMessage]) -> BaseMessage: ...


def build_explainer(model: BaseChatModel, tools: list[StructuredTool]) -> Explainer:
    return model.bind_tools(tools)  # type: ignore[return-value]
