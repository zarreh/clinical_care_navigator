# Guardrail cost

!!! warning "Not populated"
    Real per-node latency and token cost need a live LLM -- `evals/canonical.py`
    stands in a deterministic oracle for exactly that reason, so its cost is
    always $0.0000 (see `docs/evidence/evaluation.md`). The table below is
    the design, not a measurement; it fills in once A3 has a live key.

"What does all this safety cost me?" is the second question every buyer asks, and
it usually gets an opinion for an answer. This page gives it a number: added p50
and p95 latency, and added tokens, **per layer**.

The layers are not equally expensive, and the ordering is deliberate:

| Layer | Model calls | Expected cost |
|---|---|---|
| `screen_rules` | 0 | Microseconds, free |
| `classify_intent` | 1 (small model) | Low, and it runs in parallel with the screen |
| `resolve_policy` | 0 | Free |
| `critical_value` | 0 | Free — a table comparison |
| `citation_coverage` | 0 | Free — a reference check |
| `scope_judge` | 1 (larger model) | The only expensive control |

Because the two deterministic post-flight checks run first and can short-circuit
the judge, a run that escalates on a critical value costs *less* than one that
passes cleanly. Safety here is not a tax applied uniformly to every request.

This page is also the direct precursor to A4's guardrail cost accounting.
