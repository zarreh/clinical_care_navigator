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

### Attribution required by NLM

Health information displayed by this application comes from
[MedlinePlus.gov](https://medlineplus.gov/), a service of the U.S. National
Library of Medicine. MedlinePlus does not endorse this or any product, and the
MedlinePlus logo is not used here.

> This product uses publicly available data from the U.S. National Library of
> Medicine (NLM), National Institutes of Health, Department of Health and Human
> Services; NLM is not responsible for the product and does not endorse or
> recommend this or any other product.

### Terms verified before the content pipeline was written

Checked against the primary sources on 2026-08-20, not against a summary of them:

| Service | Terms | Rate limit |
|---|---|---|
| [MedlinePlus Connect](https://medlineplus.gov/medlineplus-connect/web-service/) | Free; no API key, no registration. Linking to and displaying returned data is permitted; **copying MedlinePlus pages is not**. NLM recommends caching for 12–24 hours | 100 requests/minute per IP |
| [MedlinePlus Web service](https://medlineplus.gov/about/developers/webservices/) | Free of charge; no registration or licensing. The `email` and `tool` parameters are sent, as NLM requests | 85 requests/minute per IP |
| [RxNav / RxNorm API](https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html) | Free; no licence needed for RxNorm. RxClass/SNOMED CT is **not** used, so its Affiliate licence does not apply | 20 requests/second per IP |

Accordingly this project stores only what those services return — page title,
page URL, summary and source attribution — as a **build-time cache carrying a
retrieval timestamp and a TTL**. The cache is never committed, never published,
and is not a mirror of MedlinePlus. It is rebuilt by `make data`.

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
