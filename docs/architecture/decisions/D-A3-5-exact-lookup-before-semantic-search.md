# D-A3-5: Exact lookup before semantic search

**Status:** Accepted, implemented (`retrieval/exact.py`, `retrieval/note_search.py`,
`tools/registry.py`, Phase 4).

## Context

The portfolio's engineering standard says "Qdrant everywhere" (`PORTFOLIO_PLAN_V3.md`
§9), but lab and medication education lookups have an exact key — a LOINC code
or an RxCUI — carried straight through from the record. Running a vector
search over an exact-match problem adds latency, cost and a whole failure mode
(a near-miss retrieval) for no benefit, and it is the kind of "small demo
exception" that quietly becomes a second retrieval code path if left
unexamined (§9's own warning about Chroma).

## Decision

Exact code joins are used wherever the record already carries the exact key:
`tools/lookup_lab_education.py` and `tools/lookup_medication_education.py`
resolve LOINC and RxCUI codes directly against `EducationStore`
(`retrieval/exact.py`), with no embedding step at all. Vector search
(`retrieval/note_search.py`, Qdrant-backed) is reserved for the one genuinely
open-ended retrieval problem this app has — searching a patient's own clinical
notes by topic — and it carries a **mandatory per-patient collection filter**
as a security control, not an optimisation:
`tests/retrieval/test_note_search.py` asserts a query for one patient never
returns a note whose payload `patient_id` differs.

## Consequences

- The common path (canonical cases 1, 4, 14, 15 — all lab-education lookups)
  is a SQL join with a citation attached, not a retrieval pipeline with its
  own recall/precision profile to reason about.
- "Qdrant everywhere" is scoped rather than ignored: it is used exactly where
  there is a genuine retrieval problem, and the exception is named and
  defended rather than silently taken.
- The note-search security property (never leaking another patient's note)
  is enforced at the retrieval layer itself, independent of the pre-flight
  gate and the scoped executor.
