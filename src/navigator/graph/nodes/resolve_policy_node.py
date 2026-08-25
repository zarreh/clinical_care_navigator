"""The resolve_policy node: combines the two pre-flight layers (§5.2).

Wraps the pure `resolve_policy` function, reading the rule screen's matches and
the classifier's assessment from state and writing the combined `PolicyDecision`.
Pure code — no model call. This is where the tool scope is selected, so a
non-`allow` decision binds a scope with no patient tools before any tool runs.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.nodes.resolve_policy import resolve_policy
from navigator.graph.state import NavigatorState
from navigator.store import PolicyStore
from navigator.tools.registry import ToolRegistry


def build_resolve_policy_node(
    policy_store: PolicyStore,
    registry: ToolRegistry,
    row_cap: int,
) -> Callable[[NavigatorState], dict[str, object]]:
    def resolve_policy_node(state: NavigatorState) -> dict[str, object]:
        all_matches = state["rule_matches"]
        firing = [match for match in all_matches if match.fires]
        decision = resolve_policy(
            state["question"],
            firing=firing,
            all_matches=all_matches,
            assessment=state["intent"],
            rules=policy_store.enabled_rules(),
            registry=registry,
            autonomy_level=state["autonomy_level"],  # type: ignore[arg-type]
            row_cap=row_cap,
        )
        return {"policy_decision": decision}

    return resolve_policy_node
