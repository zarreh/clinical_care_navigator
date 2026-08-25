"""Terminates a runaway run with a conservative template (docs/PLAN.md §5.5).

On a budget breach the run ends here with a conservative templated response and
the reason recorded — it never silently truncates a clinical answer.
"""

from __future__ import annotations

from navigator.graph.state import NavigatorState
from navigator.schemas.answer import PatientAnswer


def budget_exceeded_node(state: NavigatorState) -> dict[str, object]:
    answer = PatientAnswer(
        body=(
            "I'm not able to finish looking into that right now. Please message "
            "your care team through the portal, or contact your clinician's office "
            "directly if it's urgent."
        ),
        claims=[],
        citations=[],
        reading_level_target=0.0,
        reading_level_measured=None,
        autonomy_level=state.get("autonomy_level", "L2_balanced"),
        disposition="templated",
        pending_review=False,
    )
    return {"draft": answer}
