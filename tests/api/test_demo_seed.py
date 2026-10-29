"""Demo seeding of the clinician review queue.

The seeder drives scripted drafts through the real graph, post-flight and a real
SQLite checkpoint store. These tests pin that each case is held for the reason it
claims, that seeding is idempotent, and that the seeded checkpoints are durable
enough for a *different* process (the API) to resume them.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from navigator.api.demo_seed import NoA1cError, build_cases, pick_patient, seed
from navigator.api.run_executor import resume_conversation
from navigator.graph.builder import build_navigator_graph
from navigator.graph.checkpoint_serde import build_checkpoint_serde
from navigator.settings import Settings
from navigator.store import RecordStore, ReviewQueue, RunStore
from tests.api import _navigator_client as helpers
from tests.fixtures import build_fixture_stores


def _settings(tmp_path: Path) -> Settings:
    stores = build_fixture_stores(tmp_path)
    return Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
        run_store_path=str(tmp_path / "runs.db"),
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
    )


async def test_each_case_is_held_for_a_distinct_real_reason(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    results = await seed(settings)

    assert [status for _, _, status in results] == ["pending_review"] * 4
    pending = ReviewQueue(Path(settings.run_store_path)).list_pending()
    assert sorted(item.reason for item in pending) == [
        "citation_coverage",
        "citation_coverage",
        "scope_judge",
        "scope_judge",
    ]
    assert {item.run_id for item in pending} == {
        "demo-directs-action",
        "demo-contradicts-record",
        "demo-uncited-claim",
        "demo-no-information",
    }


async def test_no_information_case_holds_a_safe_canned_reply(tmp_path: Path) -> None:
    # The cholesterol scenario: the AI had nothing to look up, said so, and post-flight
    # held the honest reply because its one clinical-sounding claim had no evidence.
    settings = _settings(tmp_path)
    await seed(settings)

    run_store = RunStore(Path(settings.run_store_path))
    review = next(
        r
        for r in ReviewQueue(Path(settings.run_store_path)).list_pending()
        if r.run_id == "demo-no-information"
    )

    assert review.reason == "citation_coverage"
    assert "care team" in review.body
    run = run_store.get_run("demo-no-information")
    assert run is not None
    assert run.question == "What is the bad cholesterol?"
    # No tool was called, which is why there was nothing to cite.
    events = run_store.get_events("demo-no-information")
    investigate = [json.loads(e.payload_json) for e in events if e.node == "investigate"]
    assert investigate and all(p["tool_call_count"] == 0 for p in investigate)
    # First pass loops back for evidence, the second holds. (enqueue_review itself only
    # emits an event once a clinician decides, because it suspends at its interrupt.)
    assert [e.node for e in events].count("post_flight") == 2


async def test_seeding_twice_does_not_duplicate(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    await seed(settings)

    second = await seed(settings)

    assert [status for _, _, status in second] == ["skipped"] * 4
    assert len(ReviewQueue(Path(settings.run_store_path)).list_pending()) == 4


async def test_again_adds_fresh_copies(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    await seed(settings)

    await seed(settings, again=True)

    assert len(ReviewQueue(Path(settings.run_store_path)).list_pending()) == 8


async def test_seeded_review_resumes_from_a_separate_saver(tmp_path: Path) -> None:
    # The API is a different process from the seeder: its checkpointer is a fresh
    # connection to the same file, and must be able to resume what was seeded.
    settings = _settings(tmp_path)
    await seed(settings)
    run_store = RunStore(Path(settings.run_store_path))
    queue = ReviewQueue(Path(settings.run_store_path))
    review = next(r for r in queue.list_pending() if r.run_id == "demo-directs-action")

    async with aiosqlite.connect(settings.checkpoint_db_path) as conn:
        saver = AsyncSqliteSaver(conn, serde=build_checkpoint_serde())
        graph = build_navigator_graph(
            settings,
            intent_chain=helpers._StubIntent(),
            explainer=helpers._OneToolExplainer("unused", helpers._HBA1C),
            answer_writer_chain=helpers._FixedAnswerWriter("unused", []),
            claim_extractor_chain=helpers._FixedClaimExtractor([]),
            scope_judge_chain=helpers._FixedScopeJudge(),
            checkpointer=saver,
        )
        status = await resume_conversation(
            review,
            {"action": "edit", "edited_body": "Please discuss this with your care team."},
            graph,
            run_store,
            queue,
            settings,
        )

    assert status == "answered"
    run = run_store.get_run("demo-directs-action")
    assert run is not None
    assert run.answer_json is not None
    assert "Please discuss this with your care team." in run.answer_json


def test_contradiction_case_always_contradicts_the_actual_value(tmp_path: Path) -> None:
    store = RecordStore(Path(_settings(tmp_path).record_db_path))
    _, a1c = pick_patient(store, "")
    above = (a1c.value_number or 0.0) > 5.6

    case = next(c for c in build_cases(a1c) if c.slug == "contradicts-record")

    # Claims "within range" for an out-of-range value, and "above" for an in-range one.
    assert ("within the usual range" in case.body) == above
    assert case.judgement.contradicts_record


def test_no_patient_with_an_a1c_is_a_clear_error(tmp_path: Path) -> None:
    store = RecordStore(Path(_settings(tmp_path).record_db_path))
    with pytest.raises(NoA1cError):
        pick_patient(store, "no-such-patient")
