# D-A3-1: The sandwich has two independent halves

**Status:** Accepted, implemented (`graph/nodes/post_flight.py`, Phase 5).

## Context

A guardrail that only screens the incoming question cannot catch a case where
the question is benign but the *retrieved evidence* is dangerous — canonical
case 4, a patient asking a plain lab-education question over a potassium of
6.9 mmol/L. Most healthcare AI demos put a disclaimer in the system prompt and
call it safety; that pattern cannot produce this escalation at all, because
nothing re-examines the evidence or the draft after the pre-flight decision is
made.

## Decision

Policy runs **before** the model (`resolve_policy`) and **after** it
(`post_flight`), and the second half does not replay the first. It assesses
the retrieved evidence and the drafted answer on its own authority, through
three checks in cost order — `critical_value` (pure code), `citation_coverage`
(pure code), `scope_judge` (one model call) — and its `override_action` is
always `more_restrictive(pre_flight_action, implied)`
(`schemas/preflight.py::more_restrictive`): post-flight may escalate a run
pre-flight allowed, but it can never relax a restriction pre-flight already
imposed.

`tests/graph/test_post_flight.py::test_post_flight_never_relaxes_a_restriction`
and `tests/graph/test_post_flight_graph.py::test_benign_question_over_critical_value_escalates`
assert both halves of the property directly: the monotonic guarantee, and case
4 escalating a run pre-flight was happy to allow.

## Consequences

- The published answer's safety property depends on two independently testable
  stages, not one system prompt's discipline.
- A retrieved value can override a benign question's disposition, which is
  the entire reason case 4 is one of the three credibility cases named in
  `docs/evidence/evaluation.md`.
- Post-flight cannot be bypassed by phrasing the question carefully, since it
  never re-reads the question — it reads the evidence and the draft.
