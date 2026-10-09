"""The deterministic language-detection node (docs/PLAN.md canonical case 16).

Pure code: no model call, no network. Runs in parallel with `screen_rules` and
`classify_intent` -- detecting the question's own language is independent of
what it says.
"""

from __future__ import annotations

from navigator.graph.state import NavigatorState
from navigator.guardrails.language import detect_question_language


def detect_language_node(state: NavigatorState) -> dict[str, object]:
    return {"question_language": detect_question_language(state["question"])}
