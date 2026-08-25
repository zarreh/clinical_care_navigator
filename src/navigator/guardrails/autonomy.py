"""The autonomy band boundary (docs/PLAN.md §5.9, D-A3-3).

Bands are a property of the *question*, assigned by `resolve_policy`. The
autonomy level is a runtime setting that moves only the boundary between
`inform` and `recommend` — it **never** moves the `escalate` boundary. Red flags
escalate at every level, and there is no setting that turns that off. That
constraint is the entire point of having the setting.

- `L1 Conservative`: the boundary moves down — some `inform` questions are
  treated as `recommend` (held for clinician review).
- `L2 Balanced` (default): bands as classified.
- `L3 Permissive`: the boundary moves up — some `recommend` questions are
  answered with education plus an explicit referral.

The same question therefore produces different bands at L1/L2/L3, but identical
escalation at all three — which is the Phase 3 exit criterion.
"""

from __future__ import annotations

from navigator.schemas.preflight import Band, PolicyAction
from navigator.settings import AutonomyLevel

# The action a band maps to at each autonomy level. `escalate` is invariant:
# it maps to its escalation action regardless of level. Only the inform/recommend
# boundary moves.
#
# At L1, `inform` is held for review (treated as recommend). At L3, `recommend`
# is answered (treated as inform). `escalate` is untouched at every level.


def effective_band(classified_band: Band, autonomy_level: AutonomyLevel) -> Band:
    """Move the inform/recommend boundary per the autonomy level.

    `escalate` is returned unchanged at every level — the boundary that must
    never move.
    """
    if classified_band == "escalate":
        return "escalate"
    if autonomy_level == "L1_conservative" and classified_band == "inform":
        return "recommend"
    if autonomy_level == "L3_permissive" and classified_band == "recommend":
        return "inform"
    return classified_band


def action_for_band(band: Band, escalation_action: PolicyAction | None) -> PolicyAction:
    """Map an effective band to the action the run should take.

    For `escalate`, the specific escalation action (emergency, crisis,
    out_of_scope, clinician_review) comes from the rule that fired, so it is
    passed in. For `inform` the action is `allow`; for `recommend` it is
    `clinician_review` (the answer is drafted, held, and shown as pending
    review — §5.10).
    """
    if band == "escalate":
        assert escalation_action is not None  # noqa: S101 - escalate always has a rule
        return escalation_action
    if band == "recommend":
        return "clinician_review"
    return "allow"
