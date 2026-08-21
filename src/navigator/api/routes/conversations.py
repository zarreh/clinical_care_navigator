from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from navigator.api.deps import get_compiled_graph
from navigator.api.rate_limit import DEFAULT_RATE_LIMIT, limiter
from navigator.api.streaming import stream_graph_events
from navigator.graph.builder import SkeletonGraph
from navigator.graph.state import SkeletonState

router = APIRouter(prefix="/conversations", tags=["conversations"])

DISCLAIMER = (
    "Architectural demonstration on fully synthetic data. Not a medical device. "
    "Does not diagnose. Not a substitute for care."
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


@router.post("/stream")
@limiter.limit(DEFAULT_RATE_LIMIT)
async def stream_answer(
    request: Request,
    body: AskRequest,
    graph: Annotated[SkeletonGraph, Depends(get_compiled_graph)],
) -> EventSourceResponse:
    """Streams the graph run node by node. Phase 0 runs the walking skeleton."""
    initial: SkeletonState = {"question": body.question, "steps": []}
    return EventSourceResponse(stream_graph_events(graph, initial))
