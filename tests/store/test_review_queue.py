"""Clinician review queue (docs/PLAN.md §5.10). A held draft is enqueued once,
listed while pending, and resolved to a terminal status by the reviewer's
decision; an unknown action is rejected rather than silently stored."""

from __future__ import annotations

from pathlib import Path

import pytest

from navigator.store import ReviewQueue


def _enqueue(queue: ReviewQueue, review_id: str, run_id: str) -> None:
    queue.enqueue(
        review_id=review_id,
        run_id=run_id,
        thread_id=run_id,
        patient_id="patient-1",
        reason="scope_violation",
        override_action="clinician_review",
        body="held draft",
        payload_json='{"reason": "scope_violation"}',
    )


def test_enqueue_list_and_resolve(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    _enqueue(queue, "rev-1", "run-1")
    _enqueue(queue, "rev-2", "run-2")

    pending = queue.list_pending()
    assert {item.id for item in pending} == {"rev-1", "rev-2"}
    assert all(item.status == "pending" for item in pending)

    queue.resolve("rev-1", "approve")
    assert queue.get("rev-1").status == "approved"  # type: ignore[union-attr]
    assert {item.id for item in queue.list_pending()} == {"rev-2"}

    queue.resolve("rev-2", "edit")
    assert queue.get("rev-2").status == "edited"  # type: ignore[union-attr]
    assert queue.list_pending() == []


def test_decline_is_terminal(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    _enqueue(queue, "rev-3", "run-3")
    queue.resolve("rev-3", "decline")
    assert queue.get("rev-3").status == "declined"  # type: ignore[union-attr]


def test_unknown_action_is_rejected(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    _enqueue(queue, "rev-4", "run-4")
    with pytest.raises(ValueError):
        queue.resolve("rev-4", "not-a-real-action")


def test_unknown_review_is_none(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    assert queue.get("missing") is None


def test_claim_is_won_exactly_once(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    _enqueue(queue, "rev-5", "run-5")

    assert queue.claim("rev-5", "pending", "deciding") is True
    assert queue.claim("rev-5", "pending", "deciding") is False
    assert queue.get("rev-5").status == "deciding"  # type: ignore[union-attr]
    # A review mid-decision is not offered to another clinician.
    assert queue.list_pending() == []


def test_claim_on_unknown_review_is_false(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    assert queue.claim("missing", "pending", "deciding") is False


def test_release_stuck_decisions_returns_them_to_pending(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "runs.db")
    _enqueue(queue, "rev-6", "run-6")
    _enqueue(queue, "rev-7", "run-7")
    queue.claim("rev-6", "pending", "deciding")
    queue.resolve("rev-7", "approve")

    assert queue.release_stuck_decisions() == 1
    assert queue.get("rev-6").status == "pending"  # type: ignore[union-attr]
    assert queue.get("rev-7").status == "approved"  # type: ignore[union-attr]
