"""The deterministic question-language heuristic (docs/PLAN.md canonical case 16)."""

from __future__ import annotations

import pytest

from navigator.guardrails.language import detect_question_language

SPANISH = [
    "¿Qué significa mi resultado de A1c?",
    "Como puedo tomar mi medicina para el dolor",
    "¿Cuándo tengo que tomar mi próxima dosis?",
]

ENGLISH = [
    "What does my A1c of 7.8 mean?",
    "My son Mateo has a doctor's appointment tomorrow.",
    "Can I take ibuprofen with my current meds?",
]


@pytest.mark.parametrize("question", SPANISH)
def test_detects_spanish(question: str) -> None:
    assert detect_question_language(question) == "es"


@pytest.mark.parametrize("question", ENGLISH)
def test_does_not_flag_english(question: str) -> None:
    assert detect_question_language(question) == "en"
