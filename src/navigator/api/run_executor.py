"""Runs one patient conversation to completion, persisting every node event, the
per-node LLM cost, and the final answer to the RunStore as it happens — so a run
is replayable from the store whether the patient is watching live or reconnects
later (docs/PLAN.md §5.8). When post-flight suspends a draft for clinician
review, the run halts at a checkpoint and a ReviewItem is enqueued; a later
reviewer decision resumes it (docs/PLAN.md §5.10).

Runs as an in-process background task: a single-instance demo deployment does not
need a separate task queue (same reasoning as SQLite over Postgres, §5.2).

Redaction is deliberately *not* applied to the events written here: they feed the
patient's own SSE stream, and a person may read their own record (§5.7). The
enforced redaction boundary is the structured-log processor, installed once in
`observability`/`main`, not this store path.
"""

from __future__ import annotations

import json
import uuid

import structlog
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel

from navigator.graph.builder import NavigatorGraph
from navigator.graph.cost_tracking import CostTrackingHandler
from navigator.graph.state import NavigatorState
from navigator.observability import get_logger
from navigator.schemas.answer import PatientAnswer
from navigator.settings import Settings
from navigator.store.models import ReviewItem
from navigator.store.review_queue import ReviewQueue
from navigator.store.run_store import RunStore

logger = get_logger(__name__)

# The twelve genuine node boundaries. astream_events also emits on_chain_end for
# internal LCEL sub-steps whose names can collide with a node's langgraph_node
# tag, so filtering on name alone is not enough — see the name == node check.
_GRAPH_NODE_NAMES = frozenset(
    {
        "intake",
        "screen_rules",
        "classify_intent",
        "resolve_policy",
        "investigate",
        "draft_answer",
        "extract_claims",
        "post_flight",
        "publish",
        "enqueue_review",
        "template_response",
        "budget_exceeded",
    }
)


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)


def _build_tracing_callbacks(settings: Settings) -> list[BaseCallbackHandler]:
    if not settings.langsmith_api_key:
        return []
    from langchain_core.tracers.langchain import LangChainTracer

    return [LangChainTracer(project_name=settings.langsmith_project)]


async def execute_conversation(
    run_id: str,
    question: str,
    patient_id: str,
    graph: NavigatorGraph,
    run_store: RunStore,
    review_queue: ReviewQueue,
    settings: Settings,
) -> None:
    structlog.contextvars.bind_contextvars(correlation_id=run_id)
    cost_handler = CostTrackingHandler()
    callbacks: list[BaseCallbackHandler] = [cost_handler, *_build_tracing_callbacks(settings)]
    config: RunnableConfig = {
        "configurable": {"thread_id": run_id},
        "callbacks": callbacks,
        "metadata": {"correlation_id": run_id},
    }
    try:
        initial: NavigatorState = {
            "question": question,
            "patient_id": patient_id,
            "run_id": run_id,
        }
        final_state: dict[str, object] = {}
        sequence = 0

        async for event in graph.astream_events(initial, version="v2", config=config):
            if event["event"] != "on_chain_end":
                continue
            metadata = event.get("metadata") or {}
            node_name = metadata.get("langgraph_node")
            if node_name not in _GRAPH_NODE_NAMES or event.get("name") != node_name:
                continue
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                final_state.update(output)
            run_store.append_event(
                run_id, sequence, node_name, json.dumps(output, default=_json_default)
            )
            sequence += 1

        run_store.record_costs(run_id, list(cost_handler.entries))

        interrupt_payload = _pending_interrupt(graph, config)
        if interrupt_payload is not None:
            _enqueue_review(
                run_store, review_queue, run_id, patient_id, interrupt_payload, final_state
            )
            return
        _finalize(run_store, run_id, final_state)
    except Exception as exc:  # noqa: BLE001 — any failure must mark the run failed
        logger.error("conversation_failed", run_id=run_id, error=str(exc))
        run_store.fail_run(run_id, str(exc))
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")


def _pending_interrupt(graph: NavigatorGraph, config: RunnableConfig) -> dict[str, object] | None:
    """The review payload if the graph suspended at ``enqueue_review``, else None.

    A suspended graph has a non-empty ``next`` and carries the interrupt value on
    its pending task; that value is the review payload the node raised (§5.10).
    """
    snapshot = graph.get_state(config)
    if not snapshot.next:
        return None
    for task in snapshot.tasks:
        for interrupt in getattr(task, "interrupts", ()):  # noqa: A001 — LangGraph name
            value = getattr(interrupt, "value", None)
            if isinstance(value, dict):
                return value
    return {}


def _enqueue_review(
    run_store: RunStore,
    review_queue: ReviewQueue,
    run_id: str,
    patient_id: str,
    payload: dict[str, object],
    final_state: dict[str, object],
) -> None:
    review_id = uuid.uuid4().hex
    body = str(payload.get("body", ""))
    # Persist the held draft as a proper PatientAnswer (disposition
    # pending_review) so the conversation record reads back as structured JSON,
    # not a bare string, while still not yet published.
    draft = final_state.get("draft")
    if isinstance(draft, PatientAnswer):
        held = draft.model_copy(update={"disposition": "pending_review", "pending_review": True})
        answer_json = held.model_dump_json()
    else:
        answer_json = json.dumps({"body": body})
    review_queue.enqueue(
        review_id=review_id,
        run_id=run_id,
        thread_id=run_id,
        patient_id=patient_id,
        reason=str(payload.get("reason", "unknown")),
        override_action=(
            str(payload["override_action"]) if payload.get("override_action") is not None else None
        ),
        body=body,
        payload_json=json.dumps(payload, default=_json_default),
    )
    run_store.complete_run(
        run_id, status="pending_review", answer_kind="pending_review", answer_json=answer_json
    )
    logger.info("conversation_pending_review", run_id=run_id, review_id=review_id)


def _finalize(run_store: RunStore, run_id: str, final_state: dict[str, object]) -> None:
    published = final_state.get("published")
    if isinstance(published, PatientAnswer):
        # The run status mirrors the answer's disposition exactly
        # (answered / templated / pending_review), so a declined review that
        # leaves the draft held reads as pending_review, never answered.
        run_store.complete_run(
            run_id,
            status=published.disposition,
            answer_kind=published.disposition,
            answer_json=published.model_dump_json(),
        )
        return
    draft = final_state.get("draft")
    if isinstance(draft, PatientAnswer):
        run_store.complete_run(
            run_id, status="answered", answer_kind="draft", answer_json=draft.model_dump_json()
        )
        return
    run_store.fail_run(run_id, "graph completed without producing an answer")


async def resume_conversation(
    review: ReviewItem,
    resume_value: dict[str, object],
    graph: NavigatorGraph,
    run_store: RunStore,
    review_queue: ReviewQueue,
    settings: Settings,
) -> str:
    """Resumes a suspended run from its checkpoint with a reviewer's decision and
    persists the outcome, mirroring `execute_conversation` (docs/PLAN.md §5.10).

    Returns the run's terminal status. The resume re-enters `enqueue_review`,
    which turns the decision into a published (approve/edit) or still-held
    (decline) answer, then publish records it — every new node boundary is
    appended after the events the first pass already stored.
    """
    run_id = review.run_id
    structlog.contextvars.bind_contextvars(correlation_id=run_id)
    cost_handler = CostTrackingHandler()
    callbacks: list[BaseCallbackHandler] = [cost_handler, *_build_tracing_callbacks(settings)]
    config: RunnableConfig = {
        "configurable": {"thread_id": review.thread_id},
        "callbacks": callbacks,
        "metadata": {"correlation_id": run_id},
    }
    try:
        existing = run_store.get_events(run_id)
        sequence = existing[-1].sequence + 1 if existing else 0
        final_state: dict[str, object] = {}
        async for event in graph.astream_events(
            Command(resume=resume_value), version="v2", config=config
        ):
            if event["event"] != "on_chain_end":
                continue
            metadata = event.get("metadata") or {}
            node_name = metadata.get("langgraph_node")
            if node_name not in _GRAPH_NODE_NAMES or event.get("name") != node_name:
                continue
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                final_state.update(output)
            run_store.append_event(
                run_id, sequence, node_name, json.dumps(output, default=_json_default)
            )
            sequence += 1
        run_store.record_costs(run_id, list(cost_handler.entries))
        _finalize(run_store, run_id, final_state)
    except Exception as exc:  # noqa: BLE001 — any failure must mark the run failed
        logger.error("resume_failed", run_id=run_id, error=str(exc))
        run_store.fail_run(run_id, str(exc))
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")
    run = run_store.get_run(run_id)
    return run.status if run is not None else "failed"
