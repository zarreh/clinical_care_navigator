"""Walking-skeleton node — replaced by the real `publish` node in Phase 5."""

from navigator.graph.state import SkeletonState


def done(state: SkeletonState) -> dict[str, list[str]]:
    return {"steps": [*state["steps"], "done"]}
