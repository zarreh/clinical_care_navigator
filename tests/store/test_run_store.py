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
