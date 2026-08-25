"""API-contract request/response models — separate from ``schemas/``, which holds
the domain models the graph itself produces (docs/PLAN.md §5.8). These shape the
HTTP surface only; nothing here is persisted or fed to the graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    # Omitted means "answer as the demo patient": the API resolves a default
    # patient rather than trusting a client-supplied id for a portfolio demo.
    patient_id: str | None = Field(default=None, max_length=64)


class CreateConversationResponse(BaseModel):
    id: str
    status: str


class CostSummaryEntry(BaseModel):
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class ConversationResponse(BaseModel):
    id: str
    question: str
    patient_id: str
    status: str
    created_at: str
    updated_at: str
    answer_kind: str | None
    answer: dict[str, object] | None
    error: str | None
    total_cost_usd: float
    costs: list[CostSummaryEntry]


class ReviewSummary(BaseModel):
    id: str
    run_id: str
    patient_id: str
    reason: str
    override_action: str | None
    body: str
    status: str
    created_at: str


class ReviewDecisionRequest(BaseModel):
    action: Literal["approve", "edit", "decline"]
    # Required only for an edit; ignored otherwise.
    edited_body: str | None = Field(default=None, max_length=8_000)


class ReviewDecisionResponse(BaseModel):
    review_id: str
    run_id: str
    action: str
    run_status: str
