"""Pre-flight gate schemas (docs/PLAN.md §5.4).

The pre-flight gate has two independent layers — a deterministic rule screen and
an LLM intent classifier — combined by `resolve_policy` into a single
`PolicyDecision`. These are the typed records each layer produces and consumes.

`IntentAssessment` is the classifier's structured output: a question class, any
red flags it spotted, and a verbatim span from the question justifying the call.
`RuleMatch` is one rule firing (or being suppressed by negation/attribution) in
the deterministic screen. `PolicyDecision` is the combined, final word: the
action, the band, which rules matched, whether the two layers agreed, the tool
scope the run is bound to, and the autonomy level in force.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from navigator.schemas.scoping import ToolScope

# The five actions, in fixed severity precedence (§5.2). Higher wins; where the
# two layers disagree the more restrictive wins and the disagreement is recorded.
PolicyAction = Literal[
    "direct_to_emergency_care",
    "crisis",
    "out_of_scope",
    "clinician_review",
    "allow",
]

# Bands are a property of the question (§5.9). The autonomy setting moves only
# the inform/recommend boundary; it never moves the escalate boundary.
Band = Literal["inform", "recommend", "escalate"]

# The question classes the intent classifier can assign.
QuestionClass = Literal[
    "record_lookup",
    "lab_education",
    "medication_education",
    "decision_adjacent",
    "red_flag",
    "out_of_scope",
    "adversarial",
]


class RedFlag(BaseModel):
    """One red-flag signal the classifier spotted in the question."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(description="The red-flag category, e.g. 'cardiac', 'self_harm'.")
    span: str = Field(description="The verbatim fragment of the question carrying the signal.")


class IntentAssessment(BaseModel):
    """The intent classifier's structured output (§5.2 layer 2).

    `rationale_span` is a verbatim quote from the question, so the judgement is
    falsifiable against the actual text rather than a free-text rationale.
    """

    model_config = ConfigDict(frozen=True)

    question_class: QuestionClass
    red_flags: list[RedFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_span: str = Field(
        description="Verbatim fragment of the question that most drove this classification."
    )


class RuleMatch(BaseModel):
    """One policy rule's disposition against the question (§5.2 layer 1).

    `negated` and `attributed` are the negation/attribution context check: a
    red-flag term under a negation ("no chest pain") or inside an attribution
    ("my discharge note says to watch for chest pain") is recorded but does not
    fire — which is what makes canonical case 12 an ordinary answer.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    layer: Literal["screen_rules"] = "screen_rules"
    matched_span: str
    negated: bool = False
    attributed: bool = False

    @property
    def fires(self) -> bool:
        """A match only fires if it is neither negated nor attributed."""
        return not (self.negated or self.attributed)


class PolicyDecision(BaseModel):
    """The combined, final pre-flight decision (§5.2 `resolve_policy`).

    `layer_agreement` records whether the deterministic screen and the classifier
    landed on the same action; the disagreement rate is itself a published number
    (§5.2). `tool_scope` is the registry the run is bound to — for any non-`allow`
    action it excludes every patient tool, so refusal short-circuits before PHI
    is touched (§3.3).
    """

    model_config = ConfigDict(frozen=True)

    action: PolicyAction
    band: Band
    rule_matches: list[RuleMatch] = Field(default_factory=list)
    layer_agreement: bool
    tool_scope: ToolScope
    autonomy_level: str
    template_id: str | None = None
