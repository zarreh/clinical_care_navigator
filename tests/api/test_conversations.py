"""Conversation endpoints: create a run, read its durable record and cost, and
stream its events to completion (docs/PLAN.md §5.8). The graph is stubbed offline
and publishes without review, so the happy path lands on an answered record."""

from __future__ import annotations

import json
from pathlib import Path

from tests.api._navigator_client import build_navigator_test_context


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
    run_id = payload["id"]

    record = ctx.client.get(f"/conversations/{run_id}").json()
    assert record["status"] == "answered"
    assert record["question"] == "Explain my A1c"
    assert record["patient_id"] == ctx.patient_id
    assert record["answer"]["disposition"] == "answered"
    assert record["answer"]["body"] == "Your A1c context."
    assert "total_cost_usd" in record
    assert isinstance(record["costs"], list)


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
