"""Exit criterion (a): a suspended review resumes from a checkpoint after a
reviewer decision (docs/PLAN.md §7 Phase 6, §5.10).

The graph runs to a genuine `interrupt()` at `enqueue_review`, the run is held
`pending_review` with a queued review, and a later decision request resumes the
*same* run from its SQLite checkpoint — approve publishes the judged draft
unchanged, edit publishes an edited body — never starting a new run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from navigator.api.routes import reviews as reviews_route
from navigator.store.models import ReviewItem
from tests.api._navigator_client import NavigatorTestContext, build_navigator_test_context


def test_review_resume_approve_publishes_unchanged(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(
        tmp_path, scope_violation=True, draft_body="Here is your lab context."
    )
    create = ctx.client.post(
        "/conversations",
        json={"question": "What does my result mean?", "patient_id": ctx.patient_id},
    )
    assert create.status_code == 202
    run_id = create.json()["id"]

    # The background task ran to the interrupt: the run is held for a clinician.
    held = ctx.client.get(f"/conversations/{run_id}").json()
    assert held["status"] == "pending_review"

    reviews = ctx.client.get("/reviews").json()
    assert len(reviews) == 1
    review = reviews[0]
    assert review["run_id"] == run_id
    assert review["disclaimer"] == (
        "Architectural demonstration on fully synthetic data. Not a medical device. "
        "Does not diagnose. Not a substitute for care."
    )

    decision = ctx.client.post(f"/reviews/{review['id']}/decision", json={"action": "approve"})
    assert decision.status_code == 200
    assert decision.json()["run_status"] == "answered"
    assert decision.json()["disclaimer"]

    answered = ctx.client.get(f"/conversations/{run_id}").json()
    assert answered["status"] == "answered"
    assert answered["answer"]["disposition"] == "answered"
    assert answered["answer"]["body"] == "Here is your lab context."

    # The queue no longer offers a resolved review.
    assert ctx.client.get("/reviews").json() == []


def test_review_resume_edit_publishes_edited_body(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=True)
    run_id = ctx.client.post(
        "/conversations",
        json={"question": "What does my result mean?", "patient_id": ctx.patient_id},
    ).json()["id"]
    review = ctx.client.get("/reviews").json()[0]

    decision = ctx.client.post(
        f"/reviews/{review['id']}/decision",
        json={"action": "edit", "edited_body": "Please discuss this with your care team."},
    )
    assert decision.status_code == 200
    answered = ctx.client.get(f"/conversations/{run_id}").json()
    assert answered["status"] == "answered"
    assert answered["answer"]["body"] == "Please discuss this with your care team."


def test_edit_requires_a_body(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=True)
    ctx.client.post("/conversations", json={"question": "q", "patient_id": ctx.patient_id})
    review = ctx.client.get("/reviews").json()[0]
    resp = ctx.client.post(f"/reviews/{review['id']}/decision", json={"action": "edit"})
    assert resp.status_code == 422


def test_decision_on_unknown_review_is_404(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=True)
    resp = ctx.client.post("/reviews/does-not-exist/decision", json={"action": "approve"})
    assert resp.status_code == 404


def _held_review(tmp_path: Path) -> tuple[NavigatorTestContext, dict[str, str]]:
    ctx = build_navigator_test_context(tmp_path, scope_violation=True)
    ctx.client.post("/conversations", json={"question": "q", "patient_id": ctx.patient_id})
    return ctx, ctx.client.get("/reviews").json()[0]


def test_second_decision_on_the_same_review_is_409(tmp_path: Path) -> None:
    ctx, review = _held_review(tmp_path)
    first = ctx.client.post(f"/reviews/{review['id']}/decision", json={"action": "approve"})
    second = ctx.client.post(f"/reviews/{review['id']}/decision", json={"action": "decline"})

    assert first.status_code == 200
    assert second.status_code == 409
    assert "already approved" in second.json()["detail"]
    assert ctx.review_queue.get(review["id"]).status == "approved"  # type: ignore[union-attr]


def test_failed_resume_returns_the_review_to_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, review = _held_review(tmp_path)

    async def _failing_resume(review_item: ReviewItem, *_args: object) -> str:
        ctx.run_store.fail_run(review_item.run_id, "model unavailable")
        return "failed"

    monkeypatch.setattr(reviews_route, "resume_conversation", _failing_resume)
    resp = ctx.client.post(f"/reviews/{review['id']}/decision", json={"action": "approve"})

    assert resp.status_code == 502
    assert "model unavailable" in resp.json()["detail"]
    assert ctx.review_queue.get(review["id"]).status == "pending"  # type: ignore[union-attr]
    assert [r["id"] for r in ctx.client.get("/reviews").json()] == [review["id"]]
