# Regulatory basis

*Completed in Phase 9, with every claim cited to a primary source. This page is
the plan of record for what it will cover.*

!!! danger "Scope of this document"
    This page explains the regulatory reasoning behind the system's **design**.
    It is not legal or regulatory advice, and this system is not a medical
    device, not a clinical decision support product, and not in clinical use.

## The design constraint that shaped the architecture

The 21st Century Cures Act §3060 excludes certain clinical decision support
software from the medical device definition, and FDA's 2022 *Clinical Decision
Support Software* guidance interprets it. One criterion is that the software
enables the user to **independently review the basis** for its output rather
than relying primarily on it.

That criterion is why:

- every clinical claim carries a citation, and coverage is **measured and
  enforced** rather than requested in a prompt;
- citations point at real public-domain pages a patient can actually open — a
  citation that cannot be independently reviewed satisfies nothing;
- reference ranges are **quoted** rather than interpreted;
- the answer shows which record rows it read;
- the system directs to care rather than characterising urgency.

Citation coverage is therefore not a quality metric here. It is a design
constraint traceable to a named criterion.

## What this page will cover

| Topic | Where it lands in the build |
|---|---|
| **FDA CDS guidance (Sept 2022)** + Cures Act §3060 | Citation coverage, reviewable sources, range quoting, non-characterisation of urgency — and an explicit statement of why this design stays outside the device definition |
| **HIPAA minimum necessary** — 45 CFR 164.502(b) | Tool scoping, row caps, and refusals short-circuiting *before* retrieval |
| **HIPAA Safe Harbor de-identification** — 45 CFR 164.514(b) | The 18 identifiers, and the statement that Synthea data is synthetic and therefore not PHI at all |
| **ONC information blocking / Cures Act Final Rule** | Why patient-facing record access exists |
| **Section 1557** language access | Why literacy and language handling matter, and why Spanish is honestly deferred rather than faked |
| **988 Suicide & Crisis Lifeline** | The crisis path and its distinct template |
| Red-flag provenance | Rule by rule, with URLs |
| Reference-range provenance | Stated as illustrative and adult-general |
| MedlinePlus / RxNorm / LOINC attribution | Also in `NOTICE.md` |

## Two disclosures made deliberately

**No clinician has reviewed the safety rules.** Every emergency red-flag rule is
derived from a published patient-facing source and cites it by URL, so no rule
rests on the author's own clinical judgement. But no clinician reviewed the
resulting table. Stating that plainly is the honest position; an uncited table
reviewed informally would be worse than a cited one reviewed by nobody.

**The reference ranges are illustrative.** `data/lab_reference_ranges.csv` is
adult-general and cited to published sources. It is not any laboratory's own
reference intervals, and real ranges vary by assay, method, age and sex.
