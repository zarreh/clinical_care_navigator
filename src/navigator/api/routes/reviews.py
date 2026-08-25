"""Clinician review API (docs/PLAN.md §5.10).

`GET /reviews` lists drafts a run held for a human. `POST /reviews/{id}/decision`
resumes that exact suspended run from its LangGraph checkpoint with the decision:
approve publishes the judged draft unchanged, edit publishes an edited body, and
decline leaves it held. The decision drives the *same* interrupted run rather
than starting a new one — the durable checkpoint is what makes that possible.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from navigator.api.deps import (
    get_navigator_graph,
    get_review_queue,
    get_run_store,
    settings_dependency,
)
from navigator.api.run_executor import resume_conversation
from navigator.api.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewSummary,
)
from navigator.graph.builder import NavigatorGraph
from navigator.settings import Settings
from navigator.store import ReviewQueue, RunStore

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
async def list_reviews(
    review_queue: Annotated[ReviewQueue, Depends(get_review_queue)],
) -> list[ReviewSummary]:
    return [
        ReviewSummary(
            id=item.id,
            run_id=item.run_id,
            patient_id=item.patient_id,
            reason=item.reason,
            override_action=item.override_action,
            body=item.body,
            status=item.status,
            created_at=item.created_at,
        )
        for item in review_queue.list_pending()
    ]


@router.post("/{review_id}/decision")
async def decide_review(
    review_id: str,
    body: ReviewDecisionRequest,
    graph: Annotated[NavigatorGraph, Depends(get_navigator_graph)],
    run_store: Annotated[RunStore, Depends(get_run_store)],
    review_queue: Annotated[ReviewQueue, Depends(get_review_queue)],
    settings: Annotated[Settings, Depends(settings_dependency)],
) -> ReviewDecisionResponse:
    review = review_queue.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    if review.status != "pending":
        raise HTTPException(status_code=409, detail=f"review already {review.status}")

    resume_value: dict[str, object] = {"action": body.action}
    if body.action == "edit":
        if not body.edited_body:
            raise HTTPException(status_code=422, detail="edit requires edited_body")
        resume_value["edited_body"] = body.edited_body

    run_status = await resume_conversation(
        review, resume_value, graph, run_store, review_queue, settings
    )
    # The queue maps approve/edit/decline to its terminal status itself.
    review_queue.resolve(review_id, body.action)
    return ReviewDecisionResponse(
        review_id=review_id,
        run_id=review.run_id,
        action=body.action,
        run_status=run_status,
    )
