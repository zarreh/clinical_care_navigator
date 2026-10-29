"""Makes a follow-up question stand on its own (a conversation turn after the first).

A first question has no history, so this node returns nothing and costs nothing. A
follow-up is rewritten into a standalone question by one fast-model call, and from
then on the run is indistinguishable from any other: `question` holds the rewrite and
every guardrail applies to it as usual.

The patient's own words are kept in `original_question`. The deterministic rule screen
reads both, and the intent classifier is shown both, so a rewrite that smoothed away a
symptom or a red flag cannot lower the pre-flight decision.

If the rewrite fails or comes back empty, the run continues on the patient's own words
rather than guessing: the pre-flight gate then judges exactly what they typed.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.protocols import ContextualizerChain
from navigator.graph.state import NavigatorState
from navigator.observability import get_logger

logger = get_logger(__name__)

# Bound what is shown to the rewriter: a long earlier answer adds cost, not meaning.
_MAX_ANSWER_CHARS = 500


def format_history(history: list[dict[str, str]]) -> str:
    return "\n".join(
        f"Patient: {turn.get('question', '')}\n"
        f"Assistant: {turn.get('answer', '')[:_MAX_ANSWER_CHARS]}"
        for turn in history
    )


def build_contextualize_node(
    chain: ContextualizerChain | None,
) -> Callable[[NavigatorState], dict[str, object]]:
    def contextualize_node(state: NavigatorState) -> dict[str, object]:
        history = state.get("history") or []
        if not history or chain is None:
            return {}
        question = state["question"]
        try:
            result = chain.invoke({"history": format_history(history), "question": question})
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the patient's words
            logger.warning("contextualize_failed", error=str(exc))
            return {}
        rewritten = result.question.strip()
        if not result.is_follow_up or not rewritten or rewritten == question:
            return {}
        return {"question": rewritten, "original_question": question}

    return contextualize_node
