# D-A3-3: Autonomy is a band boundary, not a free knob

**Status:** Accepted, implemented (`guardrails/autonomy.py`, Phase 3).

## Context

The portfolio plan (`PORTFOLIO_PLAN_V3.md` §7 A3) describes three autonomy
levels — Inform, Recommend, Escalate — without saying which decisions the
setting is allowed to move. A knob that can move the escalation boundary is
not a safety-relevant control; it is a way to turn safety off, and it would
mean the same red flag could be answered directly at one setting and blocked
at another.

## Decision

Bands are a property of the *question*, assigned by `resolve_policy`. The
autonomy level moves only the boundary between `inform` and `recommend`:

- `L1_conservative` moves the boundary down — some `inform` questions are held
  for clinician review.
- `L3_permissive` moves it up — some `recommend` questions are answered with
  education plus an explicit referral.
- `escalate` is returned unchanged at **every** level
  (`guardrails/autonomy.py::effective_band`) — there is no setting that turns
  off an emergency, crisis, or out-of-scope refusal.

`tests/graph/test_resolve_policy.py::test_same_question_different_bands_across_autonomy_levels`
and `::test_identical_escalation_across_autonomy_levels` assert exactly this:
the same question produces different bands at L1/L2/L3 but identical
escalation at all three — the Phase 3 exit criterion.

## Consequences

- A clinical owner can tune how much gets held for review without being able
  to accidentally (or deliberately) loosen the emergency/crisis/out-of-scope
  boundary.
- The autonomy setting is recorded on every `PolicyDecision` and shown in the
  UI, so the knob's effect is visible rather than a silent server-side
  behaviour change.
- Case 5 (a decision-adjacent interaction question) is the one canonical case
  whose pre-flight action genuinely differs by level — held for review at
  L1/L2, answered with a pharmacist referral at L3 — and it is the only case
  `evals/canonical.py` runs three times, once per level.
