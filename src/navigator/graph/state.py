"""Graph state.

Phase 0 ships only `SkeletonState`, which exists to prove the streaming path
end to end. `NavigatorState` and its narrow per-node projections (docs/PLAN.md
§5.4) arrive in Phase 3.
"""

from typing import TypedDict


class SkeletonState(TypedDict):
    """Walking-skeleton state — replaced by `NavigatorState` in Phase 3."""

    question: str
    steps: list[str]
