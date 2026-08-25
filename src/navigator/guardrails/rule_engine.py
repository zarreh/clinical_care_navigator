"""The deterministic pre-flight screen (docs/PLAN.md §5.2 layer 1).

Compiles the policy rule table into word-boundary-aware matchers and runs them
over the question. This layer is fast, free and fully auditable — but substring
matching alone is not a guardrail (§3.2, D-A3-2). The piece that makes it
trustworthy is the **negation/attribution context check**:

- A red-flag term under a negation ("no chest pain", "denies chest pain") is
  recorded as `negated` and does not fire.
- A red-flag term inside an attribution to the record or a third party ("my
  discharge note says to watch for chest pain", "the doctor told me about chest
  pain") is recorded as `attributed` and does not fire.

That check is what makes canonical case 12 — "my discharge note says to watch
for chest pain" — an ordinary answer rather than an escalation, and it is the
single largest lever on over-refusal this layer has. A suppressed match is still
returned (with `negated`/`attributed` set) so the decision is auditable; it just
does not fire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from navigator.schemas.preflight import RuleMatch
from navigator.store.models import PolicyRule

# Window of characters before a match to inspect for a negation or attribution
# cue. Wide enough to catch "my discharge note says to watch for" but narrow
# enough that a cue in a prior clause does not suppress a real red flag.
_CONTEXT_WINDOW = 60

# Negation cues: the matched term is being denied or ruled out.
_NEGATION_RE = re.compile(
    r"\b(no|not|denies|denied|denying|without|free of|rule out|ruled out|"
    r"never had|don'?t have|do not have|haven'?t had)\b[^.!?]*$",
    re.IGNORECASE,
)

# Attribution cues: the matched term is being quoted from the record or reported
# as something a clinician said, not asserted as a current symptom.
_ATTRIBUTION_RE = re.compile(
    r"\b(note|notes|record|discharge|report|chart|doctor|nurse|provider|clinician|"
    r"they|it)\b[^.!?]*\b(says?|said|told|mention\w*|states?|stated|wrote|"
    r"watch for|warn\w*)\b[^.!?]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _CompiledRule:
    rule: PolicyRule
    pattern: re.Pattern[str]


class RuleEngine:
    """Compiles and runs the policy rule table against a question."""

    def __init__(self, rules: list[PolicyRule]) -> None:
        self._compiled = [
            _CompiledRule(rule, re.compile(rule.pattern, re.IGNORECASE))
            for rule in rules
            if rule.enabled
        ]

    def screen(self, question: str) -> list[RuleMatch]:
        """Return every rule that matched, with negation/attribution resolved.

        Both firing and suppressed matches are returned; the caller decides
        precedence over `match.fires`. A suppressed match is evidence the layer
        *saw* the term and chose not to fire — which is the auditable property.
        """
        matches: list[RuleMatch] = []
        for compiled in self._compiled:
            for found in compiled.pattern.finditer(question):
                context = question[max(0, found.start() - _CONTEXT_WINDOW) : found.start()]
                matches.append(
                    RuleMatch(
                        rule_id=compiled.rule.rule_id,
                        matched_span=found.group(0),
                        negated=bool(_NEGATION_RE.search(context)),
                        attributed=bool(_ATTRIBUTION_RE.search(context)),
                    )
                )
        return matches

    def firing(self, question: str) -> list[RuleMatch]:
        """Only the matches that actually fire (neither negated nor attributed)."""
        return [match for match in self.screen(question) if match.fires]
