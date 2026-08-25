"""Per-node LLM cost accounting (docs/PLAN.md §5.5). The estimate uses an
approximate list-price table and an unknown model prices to zero rather than
inventing a figure; the callback attributes each call to its ``langgraph_node``."""

from __future__ import annotations

from uuid import uuid4

from langchain_core.outputs import LLMResult

from navigator.graph.cost_tracking import CostTrackingHandler, estimate_cost_usd


def test_known_model_estimate() -> None:
    # 1000 prompt @ $0.15/1M + 500 completion @ $0.60/1M = 0.00015 + 0.00030.
    assert estimate_cost_usd("gpt-4o-mini", 1000, 500) == 0.00045


def test_unknown_model_prices_to_zero() -> None:
    assert estimate_cost_usd("some-unlisted-model", 1000, 500) == 0.0


def test_handler_attributes_call_to_its_node() -> None:
    handler = CostTrackingHandler()
    response = LLMResult(
        generations=[],
        llm_output={
            "model_name": "gpt-4o-mini",
            "token_usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        },
    )
    handler.on_llm_end(response, run_id=uuid4(), metadata={"langgraph_node": "draft_answer"})
    assert len(handler.entries) == 1
    entry = handler.entries[0]
    assert entry.node == "draft_answer"
    assert entry.model == "gpt-4o-mini"
    assert entry.prompt_tokens == 1000
    assert entry.completion_tokens == 500
    assert entry.cost_usd == 0.00045


def test_handler_defaults_node_to_unknown_without_metadata() -> None:
    handler = CostTrackingHandler()
    response = LLMResult(generations=[], llm_output={"model_name": "gpt-4o", "token_usage": {}})
    handler.on_llm_end(response, run_id=uuid4())
    assert handler.entries[0].node == "unknown"
    assert handler.entries[0].cost_usd == 0.0
