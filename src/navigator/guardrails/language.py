"""Detects the language of the patient's question (docs/PLAN.md canonical case 16).

A heuristic, not a model call: inverted punctuation (`¿`, `¡`), accented vowels
and `ñ`, and a small set of common Spanish function words that rarely appear in
an English sentence. It only distinguishes Spanish from English — Stage 1 is
honest that this is a stated limitation, not full language coverage (§9,
`docs/regulatory-basis.md`).
"""

from __future__ import annotations

import re

_SPANISH_CHARS_RE = re.compile(r"[¿¡ñÑáéíóúÁÉÍÓÚ]")

# Function words chosen for low collision risk with common English words (no
# "es", "son", "mi" — each is also an ordinary English word or abbreviation).
# Requiring two matches keeps a single incidental hit from tripping this.
_SPANISH_WORDS_RE = re.compile(
    r"\b(qué|como|cómo|cuál|cuáles|cuándo|dónde|porque|"
    r"significa|resultado|puedo|tomar|duele|tengo|tiene|están|está)\b",
    re.IGNORECASE,
)


def detect_question_language(question: str) -> str:
    """Return `"es"` if the question looks like Spanish, else `"en"`."""
    if _SPANISH_CHARS_RE.search(question):
        return "es"
    if len(_SPANISH_WORDS_RE.findall(question)) >= 2:
        return "es"
    return "en"
