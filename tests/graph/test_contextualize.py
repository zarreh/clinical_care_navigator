"""The contextualize node and the pre-flight changes that make a rewrite safe.

A rewrite must never be able to lower the pre-flight decision: the deterministic rule
screen reads the patient's own words as well as the rewrite, the classifier is shown
both, and language is detected on what the patient actually typed.
"""

from __future__ import annotations

from navigator.graph.nodes.classify_intent import build_classify_intent_node
from navigator.graph.nodes.contextualize import build_contextualize_node, format_history
from navigator.graph.nodes.detect_language import detect_language_node
from navigator.graph.nodes.screen_rules import build_screen_rules_node
from navigator.graph.state import NavigatorState
from navigator.schemas.preflight import IntentAssessment, RuleMatch, StandaloneQuestion

HISTORY = [{"question": "What is my A1c?", "answer": "Your A1c was 6.3%."}]


class _Chain:
    def __init__(self, result: StandaloneQuestion | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, str]] = []

    def invoke(self, input: dict[str, str]) -> StandaloneQuestion:
        self.calls.append(input)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _state(**fields: object) -> NavigatorState:
    return {"question": "what about the one before?", **fields}  # type: ignore[typeddict-item]


def test_no_history_means_no_model_call_and_no_change() -> None:
    chain = _Chain(StandaloneQuestion(question="x", is_follow_up=True))
    assert build_contextualize_node(chain)(_state()) == {}
    assert build_contextualize_node(chain)(_state(history=[])) == {}
    assert chain.calls == []


def test_a_follow_up_is_replaced_and_the_patients_words_are_kept() -> None:
    chain = _Chain(StandaloneQuestion(question="What was my previous A1c?", is_follow_up=True))

    out = build_contextualize_node(chain)(_state(history=HISTORY))

    assert out == {
        "question": "What was my previous A1c?",
        "original_question": "what about the one before?",
    }
    assert "What is my A1c?" in chain.calls[0]["history"]
    assert chain.calls[0]["question"] == "what about the one before?"


def test_a_message_that_stands_alone_is_left_alone() -> None:
    chain = _Chain(StandaloneQuestion(question="what about the one before?", is_follow_up=False))
    assert build_contextualize_node(chain)(_state(history=HISTORY)) == {}


def test_an_empty_rewrite_is_ignored() -> None:
    chain = _Chain(StandaloneQuestion(question="   ", is_follow_up=True))
    assert build_contextualize_node(chain)(_state(history=HISTORY)) == {}


def test_a_failing_rewriter_falls_back_to_the_patients_own_words() -> None:
    chain = _Chain(RuntimeError("model unavailable"))
    # No exception escapes: the run continues and pre-flight judges exactly what was typed.
    assert build_contextualize_node(chain)(_state(history=HISTORY)) == {}


def test_without_a_chain_a_follow_up_is_not_rewritten() -> None:
    assert build_contextualize_node(None)(_state(history=HISTORY)) == {}


def test_history_shown_to_the_rewriter_is_bounded() -> None:
    long_answer = "x" * 5000
    text = format_history([{"question": "q", "answer": long_answer}])
    assert len(text) < 700


# --- a rewrite cannot lower the pre-flight decision ---------------------------


class _Rules:
    """Fires on 'chest pain' anywhere in the text it is given."""

    def __init__(self) -> None:
        self.screened: list[str] = []

    def screen(self, question: str) -> list[RuleMatch]:
        self.screened.append(question)
        if "chest pain" in question.lower():
            return [RuleMatch(rule_id="cardiac", matched_span="chest pain")]
        return []


def test_the_rule_screen_reads_the_patients_words_as_well_as_the_rewrite() -> None:
    rules = _Rules()
    node = build_screen_rules_node(rules)  # type: ignore[arg-type]

    # The rewrite smoothed away the symptom; the patient's own words still carry it.
    out = node(
        _state(question="What was my previous A1c?", original_question="and my chest pain hurts")
    )

    assert rules.screened == ["What was my previous A1c?", "and my chest pain hurts"]
    assert [m.rule_id for m in out["rule_matches"]] == ["cardiac"]  # type: ignore[attr-defined]


def test_the_same_match_in_both_texts_is_reported_once() -> None:
    node = build_screen_rules_node(_Rules())  # type: ignore[arg-type]
    out = node(_state(question="my chest pain", original_question="my chest pain again?"))
    assert len(out["rule_matches"]) == 1  # type: ignore[arg-type]


def test_an_ordinary_question_is_screened_once() -> None:
    rules = _Rules()
    build_screen_rules_node(rules)(_state(question="What is my A1c?"))  # type: ignore[arg-type]
    assert rules.screened == ["What is my A1c?"]


class _Intent:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def invoke(self, input: dict[str, str]) -> IntentAssessment:
        self.seen.append(input["question"])
        return IntentAssessment(
            question_class="lab_education", red_flags=[], confidence=0.9, rationale_span="x"
        )


def test_the_classifier_is_shown_the_patients_own_words_too() -> None:
    chain = _Intent()
    build_classify_intent_node(chain)(
        _state(question="What was my previous A1c?", original_question="it still hurts, that one?")
    )
    assert "What was my previous A1c?" in chain.seen[0]
    assert "it still hurts, that one?" in chain.seen[0]


def test_the_classifier_sees_a_plain_question_unchanged() -> None:
    chain = _Intent()
    build_classify_intent_node(chain)(_state(question="What is my A1c?"))
    assert chain.seen == ["What is my A1c?"]


def test_language_is_detected_on_what_the_patient_typed() -> None:
    # The English rewrite must not make a Spanish speaker look English.
    out = detect_language_node(
        _state(question="What was my previous A1c result?", original_question="¿y el anterior?")
    )
    assert out["question_language"] != "en"
