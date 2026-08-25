"""Publishes the judged draft unchanged (docs/PLAN.md §5.3).

Deterministic, no model call: post-flight cleared the draft, so publishing is a
copy that sets the disposition to `answered` and changes nothing else. The
published body is **byte-identical** to the judged draft's body — asserted by
test — so nothing can be silently reworded after the checks that approved it.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.state import NavigatorState


def publish_node(state: NavigatorState) -> dict[str, object]:
    draft = state["draft"]
    published = draft.model_copy(update={"disposition": "answered", "pending_review": False})
    return {"published": published}


def build_publish_node() -> Callable[[NavigatorState], dict[str, object]]:
    return publish_node
