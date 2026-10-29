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
from zarreh_agentkit.cost import CostTrackingHandler
from zarreh_agentkit.serialization import iter_node_outputs, json_default

from navigator.graph.builder import NavigatorGraph
from navigator.graph.state import NavigatorState
from navigator.observability import build_tracing_callbacks, get_logger
from navigator.schemas.answer import PatientAnswer
from navigator.settings import Settings
from navigator.store.models import ReviewItem
from navigator.store.review_queue import ReviewQueue
from navigator.store.run_store import RunStore

logger = get_logger(__name__)

# The genuine node boundaries; iter_node_outputs also requires
# name == langgraph_node, which drops routing predicates and LCEL sub-steps.
_GRAPH_NODE_NAMES = frozenset(
    {
        "intake",
        "contextualize",
        "screen_rules",
        "classify_intent",
        "detect_language",
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


async def execute_conversation(
    run_id: str,
    question: str,
    patient_id: str,
    graph: NavigatorGraph,
    run_store: RunStore,
    review_queue: ReviewQueue,
    settings: Settings,
    history: list[dict[str, str]] | None = None,
) -> None:
    structlog.contextvars.bind_contextvars(correlation_id=run_id)
    cost_handler = CostTrackingHandler()
    callbacks: list[BaseCallbackHandler] = [
        cost_handler,
        *build_tracing_callbacks(settings.langsmith_api_key, settings.langsmith_project),
    ]
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
        if history:
            initial["history"] = history
        final_state: dict[str, object] = {}
        sequence = 0

        async for node_name, output in iter_node_outputs(
            graph, initial, config=config, node_names=_GRAPH_NODE_NAMES
        ):
            if isinstance(output, dict):
                final_state.update(output)
            run_store.append_event(
                run_id, sequence, node_name, json.dumps(output, default=json_default)
            )
            sequence += 1

        run_store.record_costs(run_id, cost_handler.entries)

        interrupt_payload = await _pending_interrupt(graph, config)
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


async def _pending_interrupt(
    graph: NavigatorGraph, config: RunnableConfig
) -> dict[str, object] | None:
    """The review payload if the graph suspended at ``enqueue_review``, else None.

    A suspended graph has a non-empty ``next`` and carries the interrupt value on
    its pending task; that value is the review payload the node raised (§5.10).
    Async because the production checkpointer is async-only from the event loop.
    """
    snapshot = await graph.aget_state(config)
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
        payload_json=json.dumps(payload, default=json_default),
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
    callbacks: list[BaseCallbackHandler] = [
        cost_handler,
        *build_tracing_callbacks(settings.langsmith_api_key, settings.langsmith_project),
    ]
    config: RunnableConfig = {
        "configurable": {"thread_id": review.thread_id},
        "callbacks": callbacks,
        "metadata": {"correlation_id": run_id},
    }
    try:
        existing = run_store.get_events(run_id)
        sequence = existing[-1].sequence + 1 if existing else 0
        final_state: dict[str, object] = {}
        async for node_name, output in iter_node_outputs(
            graph, Command(resume=resume_value), config=config, node_names=_GRAPH_NODE_NAMES
        ):
            if isinstance(output, dict):
                final_state.update(output)
            run_store.append_event(
                run_id, sequence, node_name, json.dumps(output, default=json_default)
            )
            sequence += 1
        run_store.record_costs(run_id, cost_handler.entries)
        _finalize(run_store, run_id, final_state)
    except Exception as exc:  # noqa: BLE001 — any failure must mark the run failed
        logger.error("resume_failed", run_id=run_id, error=str(exc))
        run_store.fail_run(run_id, str(exc))
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")
    run = run_store.get_run(run_id)
    return run.status if run is not None else "failed"


def recover_interrupted_work(run_store: RunStore, review_queue: ReviewQueue) -> None:
    """Run once at startup. Runs execute in-process, so anything still
    ``running`` was cut off by the restart and would otherwise spin forever in
    the UI; a review left ``deciding`` goes back to ``pending`` so a clinician
    can decide it again. Assumes one API process owns the run store."""
    failed = run_store.fail_interrupted_runs()
    released = review_queue.release_stuck_decisions()
    if failed or released:
        logger.warning("recovered_interrupted_work", failed_runs=failed, released_reviews=released)
