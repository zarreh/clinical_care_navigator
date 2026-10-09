"""Every graph node is traceable end to end.

`run_executor` only persists and streams events for names it lists, and the
frontend only labels names it knows. A node added to the graph but not to those
lists is silently dropped from the trace -- which is exactly what happened to
`detect_language` when it was added in Phase 8. This asserts the three lists
cannot drift apart again.
"""

from __future__ import annotations

import re
from pathlib import Path

from evals.oracle import (
    CLASSIFICATIONS,
    OracleAnswerWriter,
    OracleClaimExtractorChain,
    OracleExplainer,
    OracleIntentClassifier,
    OracleScopeJudgeChain,
)
from navigator.api.run_executor import _GRAPH_NODE_NAMES
from navigator.graph.builder import build_navigator_graph
from navigator.settings import Settings
from tests.fixtures import FixtureStores

FRONTEND_TIMELINE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "TraceTimeline.tsx"
)


def _registered_nodes(stores: FixtureStores) -> set[str]:
    settings = Settings(
        record_db_path=str(stores.records_db),
        education_db_path=str(stores.education_db),
        policy_db_path=str(stores.policy_db),
    )
    graph = build_navigator_graph(
        settings,
        intent_chain=OracleIntentClassifier(CLASSIFICATIONS["c01-lab-education"]),
        answer_writer_chain=OracleAnswerWriter(),
        explainer=OracleExplainer([]),
        claim_extractor_chain=OracleClaimExtractorChain(),
        scope_judge_chain=OracleScopeJudgeChain(),
    )
    return set(graph.get_graph().nodes) - {"__start__", "__end__"}


def test_every_registered_node_is_streamed_by_the_executor(stores: FixtureStores) -> None:
    missing = _registered_nodes(stores) - _GRAPH_NODE_NAMES
    assert not missing, f"nodes the executor would silently drop from the trace: {missing}"


def test_every_registered_node_has_a_frontend_label(stores: FixtureStores) -> None:
    labelled = set(re.findall(r"^\s{2}(\w+):\s*\"", FRONTEND_TIMELINE.read_text(), re.MULTILINE))
    missing = _registered_nodes(stores) - labelled
    assert not missing, f"nodes the timeline would show under a raw identifier: {missing}"
