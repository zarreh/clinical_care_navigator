"""Detects instruction-shaped payloads inside tool-returned text (docs/PLAN.md
canonical case 7).

Retrieved content — a clinical note in particular — is data, never an
instruction. This scanner does not alter or block what the executor returns;
the note reaches the model completely unchanged. It only records that an
instruction-shaped payload was present, so an attempt leaves a different trail
than an ordinary note (the same principle as §3.4's cross-patient recording,
applied to tool *output* instead of tool *input*).
"""

from __future__ import annotations

import re

# Deliberately blunt phrasing associated with prompt injection, not a general
# profanity/safety filter. False positives here are cheap (a recorded event
# nobody acts on); false negatives are not, so the pattern favours recall.
_INJECTION_RE = re.compile(
    r"\b(system\s*:|ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior)\s+instructions?|"
    r"disregard\s+(the\s+|all\s+)?(above|prior|previous)|"
    r"new\s+instructions?\s*:|"
    r"reveal\s+(the\s+)?(system\s+)?prompt|"
    r"act\s+as\s+(if|though)\s+you|"
    r"you\s+are\s+now\s+(a|an|in))\b",
    re.IGNORECASE,
)


def scan_for_injection(text: str) -> bool:
    """Return True if `text` contains an instruction-shaped payload."""
    return bool(_INJECTION_RE.search(text))
