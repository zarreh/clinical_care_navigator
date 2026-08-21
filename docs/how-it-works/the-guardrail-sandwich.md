# The guardrail sandwich

!!! info "In one paragraph, for a non-engineer"
    Safety checks run twice: once on the question before anything is looked up,
    and once on the answer after everything has been. The second check is not a
    repeat of the first. It looks at what was actually found in the record and
    at what the assistant actually wrote — which is the only way to catch a
    perfectly innocent question that turns out to have a dangerous answer.

## Why two halves, and why they must be independent

The obvious design checks the question, then runs the model, then re-applies the
first decision. That is one check wearing two hats, and it misses two entire
classes of risk.

**Risk that lives in the evidence, not the question.**

> *"What does my potassium of 6.9 mean?"*

That is a textbook education question. A question-only gate allows it, correctly.
The value is a medical emergency. Nothing about the *question* could have
revealed that, because the lab had not been fetched yet.

**Risk that lives in the answer.** Nothing in a question-only gate checks whether
the drafted answer diagnosed something, suggested a dose, or asserted a clinical
claim with no source behind it. Asking the model not to do those things in its
system prompt is a request, not a control.

## The three post-flight checks, in cost order

| # | Check | Kind | Catches |
|---|---|---|---|
| 1 | `critical_value` | Pure code | A retrieved lab value in a critical band, whatever the question was |
| 2 | `citation_coverage` | Pure code | A clinical claim with no resolving source |
| 3 | `scope_judge` | One model call | Diagnosis, dosing, directed clinical action, contradiction of the record |

The two deterministic checks run first, and either can short-circuit before the
expensive one. Safety here gets *cheaper*, not more expensive.

## The one rule that keeps it honest

Post-flight can **escalate** a question that pre-flight allowed. It can never
**relax** a restriction pre-flight applied. Restriction is monotonic through the
graph, and there is a test that says so.

See [Post-flight](../architecture/post-flight.md) for the implementation, and
`docs/PLAN.md` §3.1 and §5.3 in the repository for the full argument.
