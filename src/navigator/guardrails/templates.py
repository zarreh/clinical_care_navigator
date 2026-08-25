"""The four templated response branches (docs/PLAN.md §5.1).

When the pre-flight gate decides anything other than `allow`, the answer is a
**template**, not a drafted response — the run never reaches a patient tool and
never involves a model in the wording. The vocabulary is deliberate (§3.7):

- The system does not determine that an emergency exists; it detects a pattern
  on a published red-flag list and **directs to emergency care**.
- A scope control is worded as "outside what this assistant can help with" plus
  the route, never as "refusal" — the control is scope, not obstruction.
- The crisis path is distinct from the medical-emergency path, because the
  correct resource (988) and the correct wording both differ (§4.4).

Each template is a function of the matched rule (for its citation) so the
response can name the published source it rests on.
"""

from __future__ import annotations

from navigator.schemas.postflight import CriticalFinding, ScopeJudgement
from navigator.store.models import PolicyRule


def emergency_template(rule: PolicyRule | None) -> str:
    """Direct to emergency care, citing the published red-flag source."""
    basis = ""
    if rule and rule.source_name and rule.source_url:
        basis = (
            f"\n\nThis guidance is based on {rule.source_name}: "
            f'"{rule.source_quote}" ({rule.source_url})'
        )
    return (
        "Based on what you've described, please seek emergency care now — "
        "call 911 or go to the nearest emergency department. These symptoms can "
        "need immediate assessment, and only emergency care can determine that." + basis
    )


def crisis_template(rule: PolicyRule | None) -> str:
    """The dedicated self-harm crisis path, distinct from medical emergency."""
    basis = ""
    if rule and rule.source_name and rule.source_url:
        basis = f"\n\nSupport is also described at {rule.source_name} ({rule.source_url})."
    return (
        "It sounds like you may be going through something very difficult right "
        "now. Please reach out for immediate support: call or text 988 to reach "
        "the Suicide & Crisis Lifeline, available 24/7. If you are in immediate "
        "danger, call 911." + basis
    )


def out_of_scope_template(rule: PolicyRule | None) -> str:
    """Scope control, worded as a boundary plus a route — never as a refusal."""
    topic = f" ({rule.description})" if rule else ""
    return (
        f"That's outside what this assistant can help with{topic}. This kind of "
        "decision needs your own clinician, who knows your full history. You can "
        "message your care team through the portal or bring it to your next visit."
    )


def clinician_review_template(rule: PolicyRule | None) -> str:
    """A recommend-band answer is drafted, held, and shown as pending review."""
    return (
        "This is a question your care team should weigh in on. I've prepared "
        "information for them and flagged it for review — you'll see a response "
        "here once a clinician has looked at it. If your symptoms are urgent, "
        "don't wait: contact your clinician's office or emergency care directly."
    )


def critical_value_template(finding: CriticalFinding) -> str:
    """Direct to emergency care over a retrieved panic value (§5.3, case 4).

    This is the post-flight counterpart to `emergency_template`: the escalation
    was triggered not by the question but by the value itself, so the wording
    names the analyte and quotes the published threshold the reference row
    carries. It still detects a pattern against a published number and directs to
    care — it does not diagnose (§3.7).
    """
    band_word = (
        "above the critical-high" if finding.band == "critical_high" else "below the critical-low"
    )
    basis = ""
    if finding.source_name and finding.source_url and finding.source_quote:
        basis = (
            f"\n\nThis threshold is from {finding.source_name}: "
            f'"{finding.source_quote}" ({finding.source_url})'
        )
    return (
        f"One of your recent results — {finding.analyte} at {finding.value} "
        f"{finding.unit} — is {band_word} level ({finding.threshold} {finding.unit}) "
        "at which published guidance advises prompt medical attention. Please "
        "contact your care team or seek emergency care now rather than waiting. "
        "Only a clinician can assess what this value means for you." + basis
    )


def scope_violation_template(judgement: ScopeJudgement) -> str:
    """Route to a clinician when the draft crossed a scope boundary (§5.3).

    The scope judge answers four narrow questions; this names which boundary was
    crossed and quotes the draft's own span that crossed it, so the routing shows
    its basis rather than asserting "unsafe". The boundary is scope, not
    obstruction — the wording is a route to the right owner.
    """
    reasons: list[str] = []
    labels = {
        "diagnoses": "names or confirms a diagnosis",
        "changes_medication": "changes a medication or dose",
        "directs_clinical_action": "directs a specific clinical action",
        "contradicts_record": "contradicts the medical record",
    }
    for field, label in labels.items():
        if getattr(judgement, field):
            span = judgement.spans.get(field)
            reasons.append(f"{label}" + (f' ("{span}")' if span else ""))
    detail = "; ".join(reasons) if reasons else "goes beyond general information"
    return (
        "I've prepared information for your care team to review rather than "
        f"answering directly, because the response {detail}. A clinician who "
        "knows your full history should weigh in. If your symptoms are urgent, "
        "contact your clinician's office or emergency care directly."
    )


_TEMPLATES = {
    "direct_to_emergency_care": emergency_template,
    "crisis": crisis_template,
    "out_of_scope": out_of_scope_template,
    "clinician_review": clinician_review_template,
}


def render_template(action: str, rule: PolicyRule | None) -> str:
    """Render the templated response for a non-`allow` action."""
    return _TEMPLATES[action](rule)
