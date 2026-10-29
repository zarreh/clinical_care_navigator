"""The intent-classifier node (docs/PLAN.md §5.2 layer 2).

The pre-flight gate's single LLM call. Reads only the question and the patient's
literacy level — **no clinical content** (§5.4), a deliberate privacy property.
Runs in parallel with the deterministic `screen_rules`.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.protocols import IntentClassifierChain
from navigator.graph.state import NavigatorState


def build_classify_intent_node(
    chain: IntentClassifierChain,
) -> Callable[[NavigatorState], dict[str, object]]:
    def classify_intent_node(state: NavigatorState) -> dict[str, object]:
        question = state["question"]
        original = state.get("original_question")
        if original and original != question:
            # A follow-up was rewritten: show the classifier the patient's own words too,
            # so a symptom the rewrite smoothed over still drives the classification.
            question = f'{question}\n\n(The patient\'s own words: "{original}")'
        assessment = chain.invoke({"question": question})
        return {"intent": assessment}

    return classify_intent_node
