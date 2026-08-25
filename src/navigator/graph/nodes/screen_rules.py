"""The deterministic pre-flight screen node (docs/PLAN.md §5.2 layer 1).

Runs the compiled rule table over the question and records every match — firing
and suppressed — so the negation/attribution check is auditable. Pure code: no
model call, no network. Runs in parallel with `classify_intent`.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.state import NavigatorState
from navigator.guardrails.rule_engine import RuleEngine


def build_screen_rules_node(
    rule_engine: RuleEngine,
) -> Callable[[NavigatorState], dict[str, object]]:
    def screen_rules_node(state: NavigatorState) -> dict[str, object]:
        return {"rule_matches": rule_engine.screen(state["question"])}

    return screen_rules_node
