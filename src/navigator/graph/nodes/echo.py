"""Walking-skeleton node — replaced by the real `intake` node in Phase 3."""

from navigator.graph.state import SkeletonState


def echo(state: SkeletonState) -> dict[str, list[str]]:
    return {"steps": [*state["steps"], f"echo:{state['question']}"]}
