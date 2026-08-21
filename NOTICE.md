# NOTICE

## Independent implementation

This repository is an independent, clean-room implementation. The *problem
framing* — a guardrailed, patient-facing clinical education and navigation
assistant — was studied in graduate agentic-AI coursework. No course code,
notebooks, datasets, databases or documents are reproduced or redistributed
here.

Local source material used for reference during the build lives in
`reference/`, which is gitignored and never published.

## Data

All patient data is **synthetic**, generated with
[Synthea](https://github.com/synthetichealth/synthea) (Apache-2.0). This
repository contains no real, de-identified, or re-identifiable patient
information, and there is no configuration that points the application at a
real record system.

Patient education content is fetched at build time from public-domain
U.S. National Library of Medicine services:

- **MedlinePlus** and **MedlinePlus Connect** — U.S. Government work, public
  domain.
- **RxNorm / RxNav** — U.S. National Library of Medicine, public domain.

**LOINC** codes are used for laboratory identity. LOINC is a registered
trademark of Regenstrief Institute, Inc. This project uses LOINC codes that
arrive with the Synthea-generated data and does not download, embed or
redistribute the LOINC terminology table.

`data/lab_reference_ranges.csv` is original work. Every row cites the published
source of its range. It is an illustrative, adult-general demonstration table
and is not a clinical laboratory's own reference intervals.

The safety policy rules are original work. Every emergency red-flag rule cites
the published patient-facing source it was derived from. **No clinician has
reviewed these rules** — see `docs/regulatory-basis.md`.

## Not a medical device

This is an architectural demonstration. It does not diagnose, does not
recommend treatment or dosing, and is not a substitute for professional medical
care. It is not a screener, a triage tool, or a symptom checker.
