"""The four templated branches (§5.1) and their deliberate vocabulary (§3.7)."""

from __future__ import annotations

from navigator.guardrails.templates import (
    clinician_review_template,
    crisis_template,
    emergency_template,
    out_of_scope_template,
    render_template,
)
from navigator.store.models import PolicyRule


def _rule(source: bool = True) -> PolicyRule:
    return PolicyRule(
        rule_id="rf-cardiac-chest-pain",
        action="direct_to_emergency_care",
        band="escalate",
        category="cardiac",
        pattern=r"\bchest pain\b",
        description="Chest pain.",
        template_id="emergency_cardiac",
        severity=50,
        source_name="MedlinePlus — Heart Attack" if source else None,
        source_url="https://medlineplus.gov/heartattack.html" if source else None,
        source_quote="call 911" if source else None,
        version=1,
        enabled=True,
    )


def test_emergency_template_directs_and_cites() -> None:
    text = emergency_template(_rule())
    assert "911" in text
    # §3.7: the system directs to care; it does not declare an emergency.
    assert "you are having a heart attack" not in text.lower()
    # The published source is named.
    assert "medlineplus.gov" in text


def test_crisis_template_uses_988_and_is_distinct() -> None:
    text = crisis_template(_rule())
    assert "988" in text
    # Distinct resource from the medical-emergency path.
    assert "Suicide & Crisis Lifeline" in text


def test_out_of_scope_template_is_a_boundary_not_a_refusal() -> None:
    text = out_of_scope_template(None)
    # §3.7: "outside what this assistant can help with" plus the route.
    assert "outside what this assistant can help with" in text
    assert "refuse" not in text.lower()
    assert "clinician" in text.lower()


def test_clinician_review_template_states_pending_review() -> None:
    text = clinician_review_template(None)
    assert "review" in text.lower()


def test_render_template_dispatches_all_four() -> None:
    rule = _rule()
    assert "911" in render_template("direct_to_emergency_care", rule)
    assert "988" in render_template("crisis", rule)
    assert "outside what this assistant" in render_template("out_of_scope", None)
    assert "review" in render_template("clinician_review", None).lower()
