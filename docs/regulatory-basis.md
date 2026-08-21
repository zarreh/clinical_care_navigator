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

## Education-source terms, verified before the pipeline was written

The plan required these to be checked against the primary sources rather than
assumed, because the whole citation argument above rests on them.

| Service | Terms | Rate limit |
|---|---|---|
| [MedlinePlus Connect](https://medlineplus.gov/medlineplus-connect/web-service/) | Free; no API key, no registration. Linking to and displaying returned data is permitted; **copying MedlinePlus pages is not**. NLM recommends caching for 12–24 hours | 100 requests/minute per IP |
| [MedlinePlus Web service](https://medlineplus.gov/about/developers/webservices/) | Free of charge; no registration or licensing | 85 requests/minute per IP |
| [RxNav / RxNorm](https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html) | Free; no licence needed. RxClass/SNOMED CT is not used, so its Affiliate licence does not apply | 20 requests/second per IP |

So the education cache is a **build artifact**, not a corpus: it holds only the
fields the service returns — title, URL, summary, attribution — with a retrieval
timestamp and a TTL inside NLM's recommended window. It is never committed and
the application never mirrors a MedlinePlus page. Attribution appears in
`NOTICE.md`, including RxNav's required verbatim statement.

The **LOINC terminology table is deliberately not a dependency**, so its licence
agreement never applies. Synthea's observations already carry LOINC codes and
MedlinePlus Connect accepts a code directly; codes pass through, the table is
never downloaded or redistributed.

## Two disclosures made deliberately

**No clinician has reviewed the safety rules.** Every emergency red-flag rule is
derived from a published patient-facing source and cites it by URL, so no rule
rests on the author's own clinical judgement. But no clinician reviewed the
resulting table. Stating that plainly is the honest position; an uncited table
reviewed informally would be worse than a cited one reviewed by nobody.

**The reference ranges are illustrative.** `data/lab_reference_ranges.csv` is
adult-general and cited to published sources. It is not any laboratory's own
reference intervals, and real ranges vary by assay, method, age and sex.
