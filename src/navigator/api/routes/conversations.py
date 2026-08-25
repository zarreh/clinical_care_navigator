"""Patient conversation API (docs/PLAN.md §5.8).

`POST /conversations` starts a run as a background task and returns immediately
with its id; the work persists every node event to the run store as it happens.
`GET /conversations/{id}` returns the durable record and per-node cost;
`GET /conversations/{id}/events` streams the run — replaying what already
happened, then tailing to completion — so a patient can watch live or reconnect.

`POST /conversations/stream` is the Phase 0 walking-skeleton stream, kept as the
streaming proof (docs/PLAN.md §7).
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from navigator.api.deps import (
    get_compiled_graph,
    get_navigator_graph,
    get_record_store,
    get_review_queue,
    get_run_store,
    settings_dependency,
)
from navigator.api.rate_limit import DEFAULT_RATE_LIMIT, limiter
from navigator.api.run_executor import execute_conversation
from navigator.api.schemas import (
    ConversationResponse,
    CostSummaryEntry,
    CreateConversationRequest,
    CreateConversationResponse,
)
from navigator.api.streaming import stream_conversation_events, stream_graph_events
from navigator.graph.builder import NavigatorGraph, SkeletonGraph
from navigator.graph.state import SkeletonState
from navigator.settings import Settings
from navigator.store import RecordStore, ReviewQueue, RunStore

router = APIRouter(prefix="/conversations", tags=["conversations"])

DISCLAIMER = (
    "Architectural demonstration on fully synthetic data. Not a medical device. "
    "Does not diagnose. Not a substitute for care."
)


def _resolve_patient_id(
    requested: str | None, settings: Settings, record_store: RecordStore
) -> str:
    """The patient a run answers as. A portfolio demo does not trust a
    client-supplied id blindly: an explicit request is honoured, otherwise the
    configured demo patient, otherwise the first patient in the store."""
    if requested:
        return requested
    if settings.demo_patient_id:
        return settings.demo_patient_id
    patient_ids = record_store.patient_ids()
    if not patient_ids:
        raise HTTPException(status_code=503, detail="no patient records available")
    return patient_ids[0]


@router.post("", status_code=202)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    background_tasks: BackgroundTasks,
    graph: Annotated[NavigatorGraph, Depends(get_navigator_graph)],
    run_store: Annotated[RunStore, Depends(get_run_store)],
    review_queue: Annotated[ReviewQueue, Depends(get_review_queue)],
    record_store: Annotated[RecordStore, Depends(get_record_store)],
    settings: Annotated[Settings, Depends(settings_dependency)],
) -> CreateConversationResponse:
    """Starts a conversation run and returns its id; the graph runs in the
    background, persisting to the store (docs/PLAN.md §5.8)."""
    run_id = uuid.uuid4().hex
    patient_id = _resolve_patient_id(body.patient_id, settings, record_store)
    run_store.create_run(run_id, body.question, patient_id)
    background_tasks.add_task(
        execute_conversation,
        run_id,
        body.question,
        patient_id,
        graph,
        run_store,
        review_queue,
        settings,
    )
    return CreateConversationResponse(id=run_id, status="running")


@router.get("/{run_id}")
async def get_conversation(
    run_id: str,
    run_store: Annotated[RunStore, Depends(get_run_store)],
) -> ConversationResponse:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    costs = run_store.get_costs(run_id)
    return ConversationResponse(
        id=run.id,
        question=run.question,
        patient_id=run.patient_id,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        answer_kind=run.answer_kind,
        answer=json.loads(run.answer_json) if run.answer_json else None,
        error=run.error,
        total_cost_usd=round(sum(c.cost_usd for c in costs), 6),
        costs=[
            CostSummaryEntry(
                node=c.node,
                model=c.model,
                prompt_tokens=c.prompt_tokens,
                completion_tokens=c.completion_tokens,
                cost_usd=c.cost_usd,
            )
            for c in costs
        ],
    )


@router.get("/{run_id}/events")
async def stream_conversation(
    run_id: str,
    run_store: Annotated[RunStore, Depends(get_run_store)],
) -> EventSourceResponse:
    """Server-Sent Events for one conversation: replay then tail to completion."""
    if run_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return EventSourceResponse(stream_conversation_events(run_store, run_id))


@router.post("/stream")
@limiter.limit(DEFAULT_RATE_LIMIT)
async def stream_answer(
    request: Request,
    body: CreateConversationRequest,
    graph: Annotated[SkeletonGraph, Depends(get_compiled_graph)],
) -> EventSourceResponse:
    """Streams the walking-skeleton graph node by node (Phase 0 proof)."""
    initial: SkeletonState = {"question": body.question, "steps": []}
    return EventSourceResponse(stream_graph_events(graph, initial))
