# D-A3-6: Publication is deterministic, and refusals short-circuit before retrieval

**Status:** Accepted, implemented (`graph/nodes/publish.py`,
`tools/registry.py::education_only_scope`, Phase 2 and Phase 5).

## Context

Two related failure modes exist in a naive design. First, a second model call
after the safety checks pass can reintroduce exactly the problem grounding was
meant to catch — the same defect A2 found and fixed (D-A2-1), and the second
occurrence of the pattern in this portfolio. Second, a refusal that is decided
*after* patient data has already been read has already violated HIPAA's
minimum-necessary standard (45 CFR 164.502(b)), even if the answer is never
shown to the patient.

## Decision

**Publication is a plain function, not a model call.** `graph/nodes/publish.py`
builds the published answer from the already-judged draft's own
`model_copy()`, changing only `disposition` and `pending_review` — it cannot
alter the body because it never sees a prompt.
`tests/graph/test_publish.py::test_publish_is_byte_identical_to_the_judged_draft`
asserts this directly on every run.

**Refusals short-circuit before retrieval.** `resolve_policy` selects the
run's `ToolScope` as part of the pre-flight decision itself: any non-`allow`
action binds `registry.education_only_scope()`, from which every patient tool
is *absent* — not merely discouraged (`tools/registry.py`). A blocked or
refused run therefore never reaches a patient tool at all, which
`tests/graph/test_navigator_graph.py::test_emergency_question_short_circuits_before_tools`
and eight of the sixteen canonical cases (`evals/canonical.py`, the cases
tagged `no_tools`) assert with a `tool_call_count == 0` check — code, not a
policy statement.

## Consequences

- Minimum-necessary is a property of graph topology, not a downstream filter:
  a refusal is unreachable-by-construction from PHI, not merely instructed
  not to read it.
- The published answer's wording is exactly what post-flight approved — a
  reviewer reading the audit trail sees the same text the patient sees.
- The pattern generalises: the same monotonic-publication idea recurs in
  `nodes/template_response.py`'s post-flight escalation branch, which also
  never mutates the recorded pre-flight `policy_decision`.
