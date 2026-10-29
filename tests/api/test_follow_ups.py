"""Conversational follow-ups.

A conversation is a chain of runs. A follow-up names the run it continues; the API
keeps the thread's patient, attaches only to the latest finished turn, caps the length,
and the graph rewrites a context-dependent message into a standalone question before
any guardrail sees it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from navigator.api.rate_limit import limiter
from navigator.api.routes.conversations import build_history
from navigator.schemas.preflight import StandaloneQuestion
from navigator.store.models import RunRecord
from tests.api._navigator_client import NavigatorTestContext, build_navigator_test_context


@pytest.fixture(autouse=True)
def _fresh_rate_limit() -> None:
    """Each test starts several runs; the per-IP write limit is not what is under test."""
    limiter.reset()


class _Rewriter:
    """Records what it is shown, and rewrites any message containing 'that one'."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def invoke(self, input: dict[str, str]) -> StandaloneQuestion:
        self.calls.append(input)
        if "that one" in input["question"]:
            return StandaloneQuestion(
                question="What was my previous A1c result?", is_follow_up=True
            )
        return StandaloneQuestion(question=input["question"], is_follow_up=False)


def _ask(ctx: NavigatorTestContext, question: str, **extra: object) -> dict[str, object]:
    resp = ctx.client.post("/conversations", json={"question": question, **extra})
    assert resp.status_code == 202, resp.text
    return dict(resp.json())


def _events(ctx: NavigatorTestContext, run_id: str, node: str) -> list[dict[str, object]]:
    return [json.loads(e.payload_json) for e in ctx.run_store.get_events(run_id) if e.node == node]


def test_a_first_question_never_calls_the_rewriter(tmp_path: Path) -> None:
    rewriter = _Rewriter()
    ctx = build_navigator_test_context(tmp_path, scope_violation=False, contextualizer=rewriter)

    first = _ask(ctx, "What is my A1c?")

    assert rewriter.calls == []
    run = ctx.run_store.get_run(str(first["id"]))
    assert run is not None
    assert (run.conversation_id, run.turn) == (run.id, 0)
    assert _events(ctx, run.id, "contextualize") == [{}]


def test_a_follow_up_is_rewritten_and_stays_in_the_thread(tmp_path: Path) -> None:
    rewriter = _Rewriter()
    ctx = build_navigator_test_context(
        tmp_path, scope_violation=False, draft_body="Your A1c is recorded.", contextualizer=rewriter
    )
    first = _ask(ctx, "What is my A1c?")

    second = _ask(ctx, "What about that one?", follow_up_to=first["id"])

    run = ctx.run_store.get_run(str(second["id"]))
    assert run is not None
    assert run.conversation_id == first["id"]
    assert run.turn == 1
    assert run.patient_id == ctx.run_store.get_run(str(first["id"])).patient_id  # type: ignore[union-attr]
    # The rewriter saw the earlier question and the answer that was given.
    assert "What is my A1c?" in rewriter.calls[0]["history"]
    assert "Your A1c is recorded." in rewriter.calls[0]["history"]
    # The graph carried on with the rewrite, and kept the patient's own words.
    [event] = _events(ctx, run.id, "contextualize")
    assert event == {
        "question": "What was my previous A1c result?",
        "original_question": "What about that one?",
    }
    assert run.status == "answered"


def test_a_message_that_is_already_clear_is_not_rewritten(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False, contextualizer=_Rewriter())
    first = _ask(ctx, "What is my A1c?")

    second = _ask(ctx, "What is my potassium?", follow_up_to=first["id"])

    assert _events(ctx, str(second["id"]), "contextualize") == [{}]


def test_the_thread_lists_every_turn_oldest_first(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False, contextualizer=_Rewriter())
    first = _ask(ctx, "What is my A1c?")
    second = _ask(ctx, "What about that one?", follow_up_to=first["id"])

    for run_id in (first["id"], second["id"]):  # from either turn, the same thread
        thread = ctx.client.get(f"/conversations/{run_id}/thread").json()
        assert thread["conversation_id"] == first["id"]
        assert thread["patient_id"] == ctx.patient_id
        assert [(t["run_id"], t["turn"]) for t in thread["turns"]] == [
            (first["id"], 0),
            (second["id"], 1),
        ]
    assert ctx.client.get(f"/conversations/{second['id']}").json()["turn"] == 1
    assert ctx.client.get("/conversations/nope/thread").status_code == 404


# --- the guards --------------------------------------------------------------


def _error(client: TestClient, **body: object) -> tuple[int, str]:
    resp = client.post("/conversations", json={"question": "and that one?", **body})
    return resp.status_code, str(resp.json().get("detail", ""))


def test_following_up_on_an_unknown_answer_is_404(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    status, detail = _error(ctx.client, follow_up_to="nope")
    assert status == 404
    assert "not found" in detail


def test_a_follow_up_cannot_change_the_patient(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    first = _ask(ctx, "What is my A1c?")
    other = next(
        p["patient_id"]
        for p in ctx.client.get("/personas").json()
        if p["patient_id"] != ctx.run_store.get_run(str(first["id"])).patient_id  # type: ignore[union-attr]
    )

    status, detail = _error(ctx.client, follow_up_to=first["id"], patient_id=other)

    assert status == 422
    assert "same patient" in detail


def test_only_the_latest_turn_can_be_followed_up(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    first = _ask(ctx, "What is my A1c?")
    _ask(ctx, "and my potassium?", follow_up_to=first["id"])

    status, detail = _error(ctx.client, follow_up_to=first["id"])

    assert status == 409
    assert "moved on" in detail


def test_a_follow_up_waits_for_the_answer_to_finish(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    pid = ctx.patient_id
    ctx.run_store.create_run("still-going", "What is my A1c?", pid)  # status: running

    status, detail = _error(ctx.client, follow_up_to="still-going")

    assert status == 409
    assert "finish" in detail


def test_a_conversation_has_a_length_limit(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(
        tmp_path, scope_violation=False, settings_overrides={"max_conversation_turns": 2}
    )
    first = _ask(ctx, "What is my A1c?")
    second = _ask(ctx, "and my potassium?", follow_up_to=first["id"])

    status, detail = _error(ctx.client, follow_up_to=second["id"])

    assert status == 409
    assert "limit of 2" in detail


def test_two_follow_ups_cannot_fork_a_thread(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    first = _ask(ctx, "What is my A1c?")
    ctx.run_store.create_run("a", "q", ctx.patient_id, conversation_id=str(first["id"]), turn=1)

    try:
        ctx.run_store.create_run("b", "q", ctx.patient_id, conversation_id=str(first["id"]), turn=1)
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("the same turn of a conversation must not be created twice")


# --- what the rewriter is shown ----------------------------------------------


def _run(status: str, question: str, body: str | None = None) -> RunRecord:
    return RunRecord(
        id=question,
        question=question,
        patient_id="p",
        status=status,
        created_at="t",
        updated_at="t",
        answer_kind=status,
        answer_json=json.dumps({"body": body}) if body is not None else None,
        error=None,
        conversation_id="c",
        turn=0,
    )


def test_history_includes_answers_notes_held_ones_and_skips_failures() -> None:
    runs = [
        _run("answered", "q1", "a1"),
        _run("failed", "q2"),
        _run("pending_review", "q3", "unapproved draft text"),
        _run("templated", "q4", "a4"),
    ]

    history = build_history(runs, 10)

    assert [h["question"] for h in history] == ["q1", "q3", "q4"]
    assert history[0]["answer"] == "a1"
    # A held draft was never shown to the patient, so its text is not quoted.
    assert "unapproved" not in history[1]["answer"]
    assert "held for a clinician" in history[1]["answer"]


def test_history_is_limited_to_the_most_recent_turns() -> None:
    runs = [_run("answered", f"q{i}", f"a{i}") for i in range(6)]
    assert [h["question"] for h in build_history(runs, 3)] == ["q3", "q4", "q5"]
    assert build_history(runs, 0) == []
