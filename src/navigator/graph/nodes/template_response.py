"""Renders a templated response for a non-`allow` decision (docs/PLAN.md §5.1).

The four branches — emergency, crisis, out_of_scope, clinician_review — produce
a `PatientAnswer` from a template, never from a model. The run never reached a
patient tool, so the answer carries no claims and no citations; the vocabulary
is the deliberate §3.7 wording. The matched rule's citation is included where
the template rests on a published source.

This node also renders a **post-flight** escalation: when post-flight escalates
an allowed run (a retrieved critical value, or a scope judgement that the draft
diagnoses or changes a medication), the run arrives here with `post_flight` set
and no pre-flight rule. It renders the critical-value or scope-violation template
and never mutates the recorded pre-flight `policy_decision` — the pre-flight
audit trail stays exactly as it was decided (§5.3).
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.state import NavigatorState
from navigator.guardrails.templates import (
    critical_value_template,
    render_template,
    scope_violation_template,
)
from navigator.schemas.answer import PatientAnswer
from navigator.store import PolicyStore


def build_template_response_node(
    policy_store: PolicyStore,
) -> Callable[[NavigatorState], dict[str, object]]:
    def template_response_node(state: NavigatorState) -> dict[str, object]:
        post = state.get("post_flight")
        if post is not None and post.override_action is not None:
            # Post-flight escalation of an allowed run. Render from the trigger,
            # not from a pre-flight rule; the pre-flight decision is left intact.
            if post.critical_findings:
                body = critical_value_template(post.critical_findings[0])
            elif post.scope_judgement is not None:
                body = scope_violation_template(post.scope_judgement)
            else:  # pragma: no cover - defensive; an override always has a basis
                body = render_template(post.override_action, None)
            answer = PatientAnswer(
                body=body,
                claims=[],
                citations=[],
                reading_level_target=0.0,
                reading_level_measured=None,
                autonomy_level=state.get("autonomy_level", "L2_balanced"),
                disposition="templated",
                pending_review=post.override_action == "clinician_review",
            )
            return {"draft": answer, "published": answer}

        decision = state["policy_decision"]
        rule = (
            policy_store.rule(decision.rule_matches[0].rule_id) if decision.rule_matches else None
        )
        body = render_template(decision.action, rule)
        answer = PatientAnswer(
            body=body,
            claims=[],
            citations=[],
            reading_level_target=0.0,
            reading_level_measured=None,
            autonomy_level=state.get("autonomy_level", "L2_balanced"),
            disposition="templated",
            pending_review=decision.action == "clinician_review",
        )
        return {"draft": answer}

    return template_response_node
