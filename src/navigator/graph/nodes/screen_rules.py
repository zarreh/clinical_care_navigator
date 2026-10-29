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
        # A rewritten follow-up is screened as well as the patient's own words, so the
        # rewrite cannot hide a red flag the patient actually typed.
        texts = [state["question"]]
        original = state.get("original_question")
        if original and original != state["question"]:
            texts.append(original)
        matches = []
        seen: set[tuple[str, str]] = set()
        for text in texts:
            for match in rule_engine.screen(text):
                key = (match.rule_id, match.matched_span.lower())
                if key not in seen:
                    seen.add(key)
                    matches.append(match)
        return {"rule_matches": matches}

    return screen_rules_node
