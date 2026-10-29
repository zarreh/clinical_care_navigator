"""Conversation endpoints: create a run, read its durable record and cost, and
stream its events to completion (docs/PLAN.md §5.8). The graph is stubbed offline
and publishes without review, so the happy path lands on an answered record."""

from __future__ import annotations

import json
from pathlib import Path

from navigator.api.run_executor import recover_interrupted_work
from navigator.api.streaming import stream_conversation_events
from navigator.store import ReviewQueue, RunStore
from tests.api._navigator_client import build_navigator_test_context

DISCLAIMER = (
    "Architectural demonstration on fully synthetic data. Not a medical device. "
    "Does not diagnose. Not a substitute for care."
)


def test_create_then_get_returns_answered_record(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(
        tmp_path, scope_violation=False, draft_body="Your A1c context."
    )
    create = ctx.client.post(
        "/conversations", json={"question": "Explain my A1c", "patient_id": ctx.patient_id}
    )
    assert create.status_code == 202
    payload = create.json()
    assert payload["status"] == "running"
    assert payload["disclaimer"] == DISCLAIMER
    run_id = payload["id"]

    record = ctx.client.get(f"/conversations/{run_id}").json()
    assert record["status"] == "answered"
    assert record["question"] == "Explain my A1c"
    assert record["patient_id"] == ctx.patient_id
    assert record["answer"]["disposition"] == "answered"
    assert record["answer"]["body"] == "Your A1c context."
    assert "total_cost_usd" in record
    assert isinstance(record["costs"], list)
    assert record["disclaimer"] == DISCLAIMER


def test_get_unknown_conversation_is_404(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    assert ctx.client.get("/conversations/nope").status_code == 404


def test_events_replay_to_end(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    run_id = ctx.client.post(
        "/conversations", json={"question": "Explain my A1c", "patient_id": ctx.patient_id}
    ).json()["id"]

    resp = ctx.client.get(f"/conversations/{run_id}/events")
    assert resp.status_code == 200
    events = [
        json.loads(line.removeprefix("data:").strip())
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    nodes = [e["node"] for e in events]
    assert "intake" in nodes
    assert "publish" in nodes
    assert nodes[-1] == "__end__"
    assert events[-1]["output"]["status"] == "answered"


def test_events_for_unknown_conversation_is_404(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    assert ctx.client.get("/conversations/nope/events").status_code == 404


def test_unknown_patient_is_rejected_before_a_run_starts(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    resp = ctx.client.post("/conversations", json={"question": "q", "patient_id": "nobody"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "no patient record with that id"


async def test_event_tail_gives_up_on_a_run_that_never_finishes(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("stuck", "q", "patient-1")
    store.append_event("stuck", 0, "intake", "{}")

    events = [
        json.loads(chunk)
        async for chunk in stream_conversation_events(store, "stuck", max_wait_seconds=0.3)
    ]

    assert [e["node"] for e in events] == ["intake", "__end__"]
    assert events[-1]["output"]["status"] == "running"


def test_startup_recovery_fails_running_runs_and_releases_decisions(tmp_path: Path) -> None:
    run_store = RunStore(tmp_path / "runs.db")
    queue = ReviewQueue(tmp_path / "runs.db")
    run_store.create_run("cut-off", "q", "patient-1")
    queue.enqueue("rev", "held", "held", "patient-1", "scope_violation", None, "draft", "{}")
    queue.claim("rev", "pending", "deciding")

    recover_interrupted_work(run_store, queue)

    assert run_store.get_run("cut-off").status == "failed"  # type: ignore[union-attr]
    assert queue.get("rev").status == "pending"  # type: ignore[union-attr]
