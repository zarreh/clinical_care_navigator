from navigator.graph.builder import build_skeleton_graph
from navigator.graph.state import SkeletonState


def test_skeleton_graph_runs_both_nodes_in_order() -> None:
    initial: SkeletonState = {"question": "hello", "steps": []}
    result = build_skeleton_graph().invoke(initial)
    assert result["steps"] == ["echo:hello", "done"]
