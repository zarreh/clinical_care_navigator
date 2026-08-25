"""Combines the two pre-flight layers into one PolicyDecision (§5.2).

`screen_rules` (deterministic) and `classify_intent` (LLM) each produce a
decision; this node combines them by **severity precedence** — the more
restrictive action always wins — and records whether the two layers agreed. The
disagreement rate between a deterministic screen and a model classifier is
itself a published number, so it is recorded rather than smoothed over.

This node is pure code: no model call, no network. It also applies the autonomy
band boundary (§5.9) and selects the tool scope the run is bound to — for any
non-`allow` action the scope excludes every patient tool, so refusal
short-circuits before PHI is touched (§3.3).
"""

from __future__ import annotations

from navigator.guardrails.autonomy import action_for_band, effective_band
from navigator.schemas.preflight import (
    ACTION_SEVERITY,
    Band,
    IntentAssessment,
    PolicyAction,
    PolicyDecision,
    QuestionClass,
    RuleMatch,
)
from navigator.schemas.scoping import ToolScope
from navigator.settings import AutonomyLevel
from navigator.store.models import PolicyRule
from navigator.tools.registry import ToolRegistry

# Map the classifier's question class to the action/band it implies. The
# classifier never names an action directly — it classifies, and code routes.
# A red_flag class with a self_harm red flag is a crisis, not a medical
# emergency; the two paths differ in both resource and wording (§4.4).
_CLASS_TO_ACTION: dict[QuestionClass, tuple[PolicyAction, Band]] = {
    "record_lookup": ("allow", "inform"),
    "lab_education": ("allow", "inform"),
    "medication_education": ("allow", "inform"),
    "decision_adjacent": ("clinician_review", "recommend"),
    "red_flag": ("direct_to_emergency_care", "escalate"),
    "out_of_scope": ("out_of_scope", "inform"),
    "adversarial": ("out_of_scope", "inform"),
}

_CRISIS_CATEGORIES = frozenset({"self_harm"})


def _classifier_decision(assessment: IntentAssessment) -> tuple[PolicyAction, Band]:
    """The action/band the classifier implies, before combining with the screen."""
    action, band = _CLASS_TO_ACTION[assessment.question_class]
    # A self-harm red flag routes to the dedicated crisis path, not the medical
    # emergency path, regardless of the class the classifier assigned.
    if any(flag.category in _CRISIS_CATEGORIES for flag in assessment.red_flags):
        return "crisis", "escalate"
    return action, band


def _screen_decision(
    firing: list[RuleMatch], rules_by_id: dict[str, PolicyRule]
) -> tuple[PolicyAction, Band, str | None] | None:
    """The highest-severity firing rule's action/band/template, or None."""
    best: PolicyRule | None = None
    for match in firing:
        rule = rules_by_id[match.rule_id]
        if best is None or rule.severity > best.severity:
            best = rule
    if best is None:
        return None
    return best.action, best.band, best.template_id  # type: ignore[return-value]


def resolve_policy(
    question: str,
    *,
    firing: list[RuleMatch],
    all_matches: list[RuleMatch],
    assessment: IntentAssessment,
    rules: list[PolicyRule],
    registry: ToolRegistry,
    autonomy_level: AutonomyLevel,
    row_cap: int,
) -> PolicyDecision:
    """Combine the rule screen and the intent assessment into one decision.

    `firing` is the rule engine's firing matches; `all_matches` includes the
    negated/attributed ones, recorded on the decision for auditability.
    """
    rules_by_id = {rule.rule_id: rule for rule in rules}
    screen = _screen_decision(firing, rules_by_id)
    classifier_action, classifier_band = _classifier_decision(assessment)

    if screen is None:
        # No rule fired: the classifier's decision stands, with no template.
        combined_action, classified_band, template_id = classifier_action, classifier_band, None
        layer_agreement = True  # nothing to disagree with
    else:
        screen_action, screen_band, template_id = screen
        # More restrictive wins; record whether the layers agreed.
        if ACTION_SEVERITY[screen_action] >= ACTION_SEVERITY[classifier_action]:
            combined_action, classified_band = screen_action, screen_band
        else:
            combined_action, classified_band = classifier_action, classifier_band
        layer_agreement = screen_action == classifier_action

    # Apply the autonomy band boundary. It moves only the answer-vs-review
    # boundary (allow <-> clinician_review); an explicit out_of_scope refusal or
    # an escalation from either layer is authoritative and never moved (§5.9).
    if combined_action in ("allow", "clinician_review"):
        band = effective_band(classified_band, autonomy_level)
        escalation_action = combined_action if classified_band == "escalate" else None
        action = action_for_band(band, escalation_action)
    else:
        band = classified_band
        action = combined_action

    # Select the tool scope: only an `allow` decision reaches patient tools.
    scope: ToolScope = (
        registry.full_scope(row_cap=row_cap)
        if action == "allow"
        else registry.education_only_scope(row_cap=row_cap)
    )

    return PolicyDecision(
        action=action,
        band=band,
        rule_matches=all_matches,
        layer_agreement=layer_agreement,
        tool_scope=scope,
        autonomy_level=autonomy_level,
        template_id=template_id if action != "allow" else None,
    )
