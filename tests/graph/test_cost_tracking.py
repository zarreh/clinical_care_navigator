"""Per-node LLM cost accounting (docs/PLAN.md §5.5). The estimate uses an
approximate list-price table and an unknown model prices to zero rather than
inventing a figure; the callback attributes each call to its ``langgraph_node``."""

from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from navigator.graph.cost_tracking import CostTrackingHandler, estimate_cost_usd


def test_known_model_estimate() -> None:
    # 1000 prompt @ $0.15/1M + 500 completion @ $0.60/1M = 0.00015 + 0.00030.
    assert estimate_cost_usd("gpt-4o-mini", 1000, 500) == 0.00045


def test_unknown_model_prices_to_zero() -> None:
    assert estimate_cost_usd("some-unlisted-model", 1000, 500) == 0.0


def test_dated_model_name_resolves_to_its_family_price() -> None:
    # OpenAI reports the dated snapshot, never the bare alias the price table is keyed on.
    assert estimate_cost_usd("gpt-4o-mini-2024-07-18", 1000, 500) == 0.00045
    assert estimate_cost_usd("gpt-4o-2024-08-06", 1000, 500) == 0.0075


def _run_call(
    handler: CostTrackingHandler,
    *,
    node: str | None,
    llm_output: dict[str, object] | None,
    usage_metadata: dict[str, int] | None = None,
    response_model: str | None = None,
) -> None:
    """Drives the handler the way LangChain does: the node tag arrives on the start
    event only, and the end event carries neither metadata nor, for structured
    output, an `llm_output`."""
    run_id = uuid4()
    handler.on_chat_model_start(
        {},
        [],
        run_id=run_id,
        metadata={"langgraph_node": node} if node else {},
    )
    message = AIMessage(
        content="",
        usage_metadata=usage_metadata,
        response_metadata={"model_name": response_model} if response_model else {},
    )
    handler.on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=message)]], llm_output=llm_output),
        run_id=run_id,
    )


def test_handler_attributes_call_to_its_node() -> None:
    handler = CostTrackingHandler()
    _run_call(
        handler,
        node="draft_answer",
        llm_output={
            "model_name": "gpt-4o-mini-2024-07-18",
            "token_usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        },
    )
    assert len(handler.entries) == 1
    entry = handler.entries[0]
    assert entry.node == "draft_answer"
    assert entry.model == "gpt-4o-mini-2024-07-18"
    assert entry.prompt_tokens == 1000
    assert entry.completion_tokens == 500
    assert entry.cost_usd == 0.00045


def test_structured_output_call_falls_back_to_message_usage() -> None:
    handler = CostTrackingHandler()
    _run_call(
        handler,
        node="classify_intent",
        llm_output=None,
        usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        response_model="gpt-4o-mini-2024-07-18",
    )
    entry = handler.entries[0]
    assert entry.node == "classify_intent"
    assert (entry.prompt_tokens, entry.completion_tokens) == (1000, 500)
    assert entry.model == "gpt-4o-mini-2024-07-18"
    assert entry.cost_usd == 0.00045


def test_handler_defaults_node_to_unknown_without_metadata() -> None:
    handler = CostTrackingHandler()
    _run_call(handler, node=None, llm_output={"model_name": "gpt-4o", "token_usage": {}})
    assert handler.entries[0].node == "unknown"
    assert handler.entries[0].cost_usd == 0.0
