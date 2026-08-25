"""Renders a templated response for a non-`allow` decision (docs/PLAN.md §5.1).

The four branches — emergency, crisis, out_of_scope, clinician_review — produce
a `PatientAnswer` from a template, never from a model. The run never reached a
patient tool, so the answer carries no claims and no citations; the vocabulary
is the deliberate §3.7 wording. The matched rule's citation is included where
the template rests on a published source.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.state import NavigatorState
from navigator.guardrails.templates import render_template
from navigator.schemas.answer import PatientAnswer
from navigator.store import PolicyStore


def build_template_response_node(
    policy_store: PolicyStore,
) -> Callable[[NavigatorState], dict[str, object]]:
    def template_response_node(state: NavigatorState) -> dict[str, object]:
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
