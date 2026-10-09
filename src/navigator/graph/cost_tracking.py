"""Per-node LLM cost accounting via a LangChain callback (docs/PLAN.md §5.5).

LangGraph tags every node's LLM calls with ``langgraph_node`` in the run
metadata, so one callback attached to the whole graph invocation attributes each
call's tokens back to the node that made it — no manual plumbing through node
code. Kept local rather than pulled from a shared kit (§0.3): a cost meter is
small enough to own, and owning it keeps the price table honest and in view.

The prices are approximate list prices for the estimate shown on the cost meter,
not a billing-grade figure — real prices change often and are not the point.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from navigator.store.models import CostEntry

# USD per 1M tokens (prompt, completion). Covers the models this app configures.
PRICE_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimated USD cost of one LLM call at the approximate list price.

    An unknown model prices to zero rather than guessing — a cost meter that
    invents a number for a model it does not know is worse than one that admits
    it does not know. OpenAI reports dated snapshots (``gpt-4o-mini-2024-07-18``),
    so a model prices as its longest listed family name.
    """
    family = max(
        (
            name
            for name in PRICE_PER_MILLION_TOKENS
            if model == name or model.startswith(f"{name}-")
        ),
        key=len,
        default=None,
    )
    prompt_price, completion_price = PRICE_PER_MILLION_TOKENS.get(family or "", (0.0, 0.0))
    return (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000


def _call_usage(response: LLMResult) -> tuple[str, int, int]:
    """(model, prompt_tokens, completion_tokens). Structured-output calls leave
    ``llm_output`` empty, so the message's own usage metadata is the fallback."""
    llm_output = response.llm_output or {}
    usage = llm_output.get("token_usage") or {}
    model = str(llm_output.get("model_name") or "unknown")
    prompt = int(usage.get("prompt_tokens", 0))
    completion = int(usage.get("completion_tokens", 0))
    if prompt or completion:
        return model, prompt, completion
    for generations in response.generations:
        for generation in generations:
            message = getattr(generation, "message", None)
            usage_metadata = getattr(message, "usage_metadata", None)
            if usage_metadata:
                reported = (getattr(message, "response_metadata", None) or {}).get("model_name")
                return (
                    str(reported or model),
                    int(usage_metadata.get("input_tokens", 0)),
                    int(usage_metadata.get("output_tokens", 0)),
                )
    return model, prompt, completion


class CostTrackingHandler(BaseCallbackHandler):
    """Attach once per graph invocation via ``config={"callbacks": [...]}``;
    ``entries`` accumulates one :class:`CostEntry` per completed LLM call."""

    def __init__(self) -> None:
        self.entries: list[CostEntry] = []
        # LangChain delivers run metadata (and so the node tag) on the start event only.
        self._nodes: dict[UUID, str] = {}

    def _remember_node(self, run_id: UUID, metadata: dict[str, Any] | None) -> None:
        self._nodes[run_id] = str((metadata or {}).get("langgraph_node", "unknown"))

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._remember_node(run_id, metadata)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._remember_node(run_id, metadata)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        model, prompt_tokens, completion_tokens = _call_usage(response)
        self.entries.append(
            CostEntry(
                node=self._nodes.pop(run_id, "unknown"),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=estimate_cost_usd(model, prompt_tokens, completion_tokens),
            )
        )
