"""The production checkpointer is `AsyncSqliteSaver`; every other test uses `MemorySaver`,
which tolerates synchronous state reads from async code and hid a failure on every real run."""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from navigator.api.run_executor import execute_conversation
from navigator.graph.builder import build_navigator_graph
from navigator.schemas.answer import Claim
from navigator.settings import Settings
from navigator.store import ReviewQueue, RunStore
from tests.api import _navigator_client as helpers
from tests.fixtures import build_fixture_stores


async def test_run_completes_on_the_real_async_sqlite_checkpointer(tmp_path: Path) -> None:
    stores = build_fixture_stores(tmp_path)
    run_db = tmp_path / "runs.db"
    settings = Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
        run_store_path=str(run_db),
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
    )
    patient_id = stores.patient_ids[0]
    claim = Claim(
        id="c1", text="Your result is recorded.", kind="clinical", evidence_refs=["call-1"]
    )
    run_store = RunStore(run_db)
    run_store.create_run("run-1", "Explain my A1c", patient_id)

    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as saver:
        graph = build_navigator_graph(
            settings,
            intent_chain=helpers._StubIntent(),
            explainer=helpers._OneToolExplainer(patient_id, helpers._HBA1C),
            answer_writer_chain=helpers._FixedAnswerWriter("Your A1c context.", [claim]),
            claim_extractor_chain=helpers._FixedClaimExtractor([claim]),
            scope_judge_chain=helpers._FixedScopeJudge(),
            checkpointer=saver,
        )
        await execute_conversation(
            "run-1", "Explain my A1c", patient_id, graph, run_store, ReviewQueue(run_db), settings
        )

    run = run_store.get_run("run-1")
    assert run is not None
    assert run.error is None, run.error
    assert run.status == "answered"
