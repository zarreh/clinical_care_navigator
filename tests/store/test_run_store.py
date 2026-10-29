"""Durable conversation store: a run replays from persisted events whether a
client watches live or reconnects later, and per-node cost is attributed
(docs/PLAN.md §5.8, §5.5)."""

from __future__ import annotations

from pathlib import Path

from navigator.store import RunStore
from navigator.store.models import CostEntry


def test_run_lifecycle_and_event_replay(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("r1", "What is my A1c?", "patient-1")

    run = store.get_run("r1")
    assert run is not None
    assert run.status == "running"
    assert run.question == "What is my A1c?"
    assert run.patient_id == "patient-1"

    store.append_event("r1", 0, "intake", '{"question": "What is my A1c?"}')
    store.append_event("r1", 1, "investigate", '{"evidence": []}')
    store.append_event("r1", 2, "publish", '{"published": {}}')

    # Full replay from the start.
    replay = store.get_events("r1")
    assert [e.sequence for e in replay] == [0, 1, 2]
    assert [e.node for e in replay] == ["intake", "investigate", "publish"]

    # Tail: only events after the last one a client already saw.
    tail = store.get_events("r1", after_sequence=1)
    assert [e.sequence for e in tail] == [2]

    store.complete_run(
        "r1", status="answered", answer_kind="published", answer_json='{"body": "ok"}'
    )
    completed = store.get_run("r1")
    assert completed is not None
    assert completed.status == "answered"
    assert completed.answer_kind == "published"
    assert completed.answer_json == '{"body": "ok"}'


def test_costs_are_recorded_and_read_back(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("r2", "q", "p")
    store.record_costs(
        "r2",
        [
            CostEntry("classify_intent", "gpt-4o-mini", 1000, 200, 0.00027),
            CostEntry("draft_answer", "gpt-4o", 2000, 800, 0.013),
        ],
    )
    costs = store.get_costs("r2")
    assert {c.node for c in costs} == {"classify_intent", "draft_answer"}
    assert round(sum(c.cost_usd for c in costs), 5) == round(0.00027 + 0.013, 5)


def test_fail_run_records_error(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("r3", "q", "p")
    store.fail_run("r3", "boom")
    run = store.get_run("r3")
    assert run is not None
    assert run.status == "failed"
    assert run.error == "boom"


def test_unknown_run_is_none(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    assert store.get_run("missing") is None
    assert store.get_events("missing") == []


def test_fail_interrupted_runs_only_touches_running(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("live", "q", "patient-1")
    store.create_run("done", "q", "patient-1")
    store.complete_run("done", status="answered", answer_kind="answered", answer_json="{}")

    assert store.fail_interrupted_runs() == 1

    live = store.get_run("live")
    assert live is not None
    assert live.status == "failed"
    assert live.error is not None and "restart" in live.error
    assert store.get_run("done").status == "answered"  # type: ignore[union-attr]
    assert store.fail_interrupted_runs() == 0


def test_a_run_starts_its_own_conversation_by_default(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("r1", "q", "p")

    run = store.get_run("r1")

    assert run is not None
    assert (run.conversation_id, run.turn) == ("r1", 0)


def test_conversation_runs_are_returned_oldest_first(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    store.create_run("r1", "q1", "p")
    store.create_run("r2", "q2", "p", conversation_id="r1", turn=1)
    store.create_run("r3", "q3", "p", conversation_id="r1", turn=2)
    store.create_run("other", "q", "p")

    assert [r.id for r in store.conversation_runs("r1")] == ["r1", "r2", "r3"]
    assert [r.id for r in store.conversation_runs("other")] == ["other"]


def test_a_turn_of_a_conversation_cannot_be_created_twice(tmp_path: Path) -> None:
    import sqlite3

    import pytest

    store = RunStore(tmp_path / "runs.db")
    store.create_run("r1", "q1", "p")
    store.create_run("r2", "q2", "p", conversation_id="r1", turn=1)

    with pytest.raises(sqlite3.IntegrityError):
        store.create_run("r3", "q3", "p", conversation_id="r1", turn=1)


def test_a_database_from_before_follow_ups_is_migrated_in_place(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "old.db"
    legacy = sqlite3.connect(db)
    legacy.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, question TEXT NOT NULL, patient_id TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            answer_kind TEXT, answer_json TEXT, error TEXT
        );
        INSERT INTO conversations (id, question, patient_id, status, created_at, updated_at)
            VALUES ('old-run', 'What is my A1c?', 'p', 'answered', 't', 't');
        """
    )
    legacy.commit()
    legacy.close()

    store = RunStore(db)

    run = store.get_run("old-run")
    assert run is not None
    assert (run.conversation_id, run.turn) == ("old-run", 0)
    # ...and it can be followed up like any other run.
    store.create_run("new-run", "and the other?", "p", conversation_id="old-run", turn=1)
    assert [r.id for r in store.conversation_runs("old-run")] == ["old-run", "new-run"]
    # Opening it again is a no-op.
    RunStore(db)
