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
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from navigator.api.deps import (
    get_compiled_graph,
    get_navigator_graph,
    get_personas,
    get_record_store,
    get_review_queue,
    get_run_store,
    settings_dependency,
)
from navigator.api.personas import Persona
from navigator.api.rate_limit import READ_RATE_LIMIT, WRITE_RATE_LIMIT, limiter
from navigator.api.run_executor import execute_conversation
from navigator.api.schemas import (
    ConversationResponse,
    CostSummaryEntry,
    CreateConversationRequest,
    CreateConversationResponse,
    ThreadResponse,
    ThreadTurn,
)
from navigator.api.streaming import stream_conversation_events, stream_graph_events
from navigator.graph.builder import NavigatorGraph, SkeletonGraph
from navigator.graph.state import SkeletonState
from navigator.settings import Settings
from navigator.store import RecordStore, ReviewQueue, RunStore
from navigator.store.models import RunRecord

router = APIRouter(prefix="/conversations", tags=["conversations"])

_STREAM_GRACE_SECONDS = 60.0


def _resolve_patient_id(
    requested: str | None,
    settings: Settings,
    record_store: RecordStore,
    personas: Sequence[Persona],
) -> str:
    """The patient a run answers as. A portfolio demo does not trust a
    client-supplied id blindly: it only answers as a demonstration persona. With no
    request it uses the configured demo patient, else the first persona."""
    allowed = {p.patient_id for p in personas}
    if settings.demo_patient_id:
        allowed.add(settings.demo_patient_id)
    if requested:
        # Fail here with a clear 404, not later inside a background task the
        # client never sees.
        if record_store.get_patient(requested) is None:
            raise HTTPException(status_code=404, detail="no patient record with that id")
        if settings.demo_patients_only and requested not in allowed:
            raise HTTPException(
                status_code=404,
                detail="that patient is not one of the demo personas (see GET /personas)",
            )
        return requested
    if settings.demo_patient_id:
        return settings.demo_patient_id
    if personas:
        return personas[0].patient_id
    patient_ids = record_store.patient_ids()
    if not patient_ids:
        raise HTTPException(status_code=503, detail="no patient records available")
    return patient_ids[0]


@dataclass(frozen=True)
class _FollowUp:
    patient_id: str
    conversation_id: str
    turn: int
    history: list[dict[str, str]]


_HELD_NOTE = "(This answer was held for a clinician and has not been shown as answered.)"


def build_history(runs: Sequence[RunRecord], limit: int) -> list[dict[str, str]]:
    """The last `limit` finished turns as {question, answer} for the rewriter. A run that
    failed or is still going has no answer; a held one is noted, not quoted."""
    turns: list[dict[str, str]] = []
    for run in runs[-limit:] if limit > 0 else []:
        if run.status in ("answered", "templated") and run.answer_json:
            answer = str(json.loads(run.answer_json).get("body", ""))
        elif run.status == "pending_review":
            answer = _HELD_NOTE
        else:
            continue
        turns.append({"question": run.question, "answer": answer})
    return turns


def _plan_follow_up(
    body: CreateConversationRequest, run_store: RunStore, settings: Settings
) -> _FollowUp:
    """Validates a follow-up and works out where it sits. A follow-up keeps its
    conversation's patient (a thread never changes whose record it is about), attaches
    only to the latest turn, and waits for that turn to finish."""
    previous = run_store.get_run(body.follow_up_to or "")
    if previous is None:
        raise HTTPException(
            status_code=404, detail="The answer you are following up on was not found."
        )
    if body.patient_id and body.patient_id != previous.patient_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "A follow-up stays with the same patient. "
                "Start a new conversation to ask as someone else."
            ),
        )
    runs = run_store.conversation_runs(previous.conversation_id)
    if runs[-1].id != previous.id:
        raise HTTPException(
            status_code=409,
            detail="This conversation has moved on. Follow up on its latest answer.",
        )
    if previous.status == "running":
        raise HTTPException(
            status_code=409, detail="Wait for the answer to finish before asking a follow-up."
        )
    if len(runs) >= settings.max_conversation_turns:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This conversation has reached its limit of {settings.max_conversation_turns} "
                "questions. Start a new one."
            ),
        )
    return _FollowUp(
        patient_id=previous.patient_id,
        conversation_id=previous.conversation_id,
        turn=previous.turn + 1,
        history=build_history(runs, settings.conversation_context_turns),
    )


@router.post("", status_code=202)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    background_tasks: BackgroundTasks,
    graph: Annotated[NavigatorGraph, Depends(get_navigator_graph)],
    run_store: Annotated[RunStore, Depends(get_run_store)],
    review_queue: Annotated[ReviewQueue, Depends(get_review_queue)],
    record_store: Annotated[RecordStore, Depends(get_record_store)],
    personas: Annotated[tuple[Persona, ...], Depends(get_personas)],
    settings: Annotated[Settings, Depends(settings_dependency)],
) -> CreateConversationResponse:
    """Starts a conversation run and returns its id; the graph runs in the
    background, persisting to the store (docs/PLAN.md §5.8)."""
    run_id = uuid.uuid4().hex
    conversation_id: str | None = None
    turn = 0
    history: list[dict[str, str]] = []
    if body.follow_up_to:
        follow_up = _plan_follow_up(body, run_store, settings)
        patient_id, conversation_id, turn, history = (
            follow_up.patient_id,
            follow_up.conversation_id,
            follow_up.turn,
            follow_up.history,
        )
    else:
        patient_id = _resolve_patient_id(body.patient_id, settings, record_store, personas)
    try:
        run_store.create_run(
            run_id, body.question, patient_id, conversation_id=conversation_id, turn=turn
        )
    except sqlite3.IntegrityError as exc:
        # Two follow-ups raced for the same turn; the first one won.
        raise HTTPException(
            status_code=409,
            detail="Another follow-up was just asked on this answer. Refresh to see it.",
        ) from exc
    background_tasks.add_task(
        execute_conversation,
        run_id,
        body.question,
        patient_id,
        graph,
        run_store,
        review_queue,
        settings,
        history,
    )
    return CreateConversationResponse(id=run_id, status="running")


@router.get("/{run_id}")
@limiter.limit(READ_RATE_LIMIT)
async def get_conversation(
    request: Request,
    run_id: str,
    run_store: Annotated[RunStore, Depends(get_run_store)],
) -> ConversationResponse:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    costs = run_store.get_costs(run_id)
    return ConversationResponse(
        id=run.id,
        conversation_id=run.conversation_id,
        turn=run.turn,
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


@router.get("/{run_id}/thread")
@limiter.limit(READ_RATE_LIMIT)
async def get_thread(
    request: Request,
    run_id: str,
    run_store: Annotated[RunStore, Depends(get_run_store)],
) -> ThreadResponse:
    """Every turn of the conversation this run belongs to, oldest first."""
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return ThreadResponse(
        conversation_id=run.conversation_id,
        patient_id=run.patient_id,
        turns=[
            ThreadTurn(run_id=r.id, turn=r.turn, question=r.question, status=r.status)
            for r in run_store.conversation_runs(run.conversation_id)
        ],
    )


@router.get("/{run_id}/events")
@limiter.limit(READ_RATE_LIMIT)
async def stream_conversation(
    request: Request,
    run_id: str,
    run_store: Annotated[RunStore, Depends(get_run_store)],
    settings: Annotated[Settings, Depends(settings_dependency)],
) -> EventSourceResponse:
    """Server-Sent Events for one conversation: replay then tail to completion."""
    if run_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    # The run itself is budgeted to max_run_seconds; the grace covers a slow
    # final LLM call so a healthy run is never cut off mid-stream.
    max_wait = settings.max_run_seconds + _STREAM_GRACE_SECONDS
    return EventSourceResponse(stream_conversation_events(run_store, run_id, max_wait))


@router.post("/stream")
@limiter.limit(WRITE_RATE_LIMIT)
async def stream_answer(
    request: Request,
    body: CreateConversationRequest,
    graph: Annotated[SkeletonGraph, Depends(get_compiled_graph)],
) -> EventSourceResponse:
    """Streams the walking-skeleton graph node by node (Phase 0 proof)."""
    initial: SkeletonState = {"question": body.question, "steps": []}
    return EventSourceResponse(stream_graph_events(graph, initial))
