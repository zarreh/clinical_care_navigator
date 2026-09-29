# D-A3-4: Citations are real, and that is free

**Status:** Accepted, implemented (`data/fetch_education.py`, Phase 1).

## Context

A citation-grounded patient assistant is only as credible as its citations.
Fabricating a plausible-looking source, or substituting a similar-but-wrong
page when the exact one is missing, is not a data-quality problem in this
project — it is a category error, because citation coverage is the design
constraint that keeps the app outside the FDA's Clinical Decision Support
device definition (`docs/regulatory-basis.md`, §6.1 in the build plan).

## Decision

Education citations resolve to real, public-domain sources — MedlinePlus
Connect and RxNav/RxNorm — free and key-less, never LLM-generated content.
The LOINC code table itself is not a dependency at all: Synthea's own
`observations.csv` already carries the codes, so the exact-match citation
path never needs to license or ship the table
(`store/models.py::Observation.loinc_code`). Where no vetted page exists for a
code, `tools/lookup_lab_education.py` returns a declared `CoverageGap` — never
a substituted near-match and never generated text.

`tests/tools/test_tools.py::test_lookup_lab_education_declares_gap_for_uncovered_code`
and canonical case 14 (`evals/canonical.py`, *"what did my \{analyte\} come
back as?"*) assert the declared-gap path directly: the answer states the gap,
it does not fabricate a result.

## Consequences

- Every citation a reader sees is a link they can actually open and verify —
  the FDA CDS "independently review the basis" criterion, satisfied by
  construction rather than by prompt instruction.
- Coverage gaps are a measured build statistic
  (`docs/evidence/data-profile.md`), not a surprise found in production.
- `NOTICE.md` carries the exact attribution MedlinePlus Connect and RxNav
  require; nothing here copies a MedlinePlus page verbatim.
