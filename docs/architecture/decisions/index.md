# Architecture decisions

Six decisions, each with a short record. They arrive with the phase that
implements them; the table below is the plan of record (`docs/PLAN.md` §12).

| id | Decision | Phase |
|---|---|---|
| **D-A3-1** | **The sandwich has two independent halves.** Post-flight assesses the retrieved evidence and the drafted answer on its own authority — it does not replay the pre-flight decision. It may escalate; it may never relax | 5 |
| **D-A3-2** | **Substring matching is not a guardrail.** A deterministic pattern layer with negation and attribution handling, plus one structured classifier call, combined by code with fixed severity precedence. Both directions of error are measured | 3 |
| **D-A3-3** | **Autonomy is a band boundary, not a free knob.** Bands are a property of the question; the setting moves only the inform/recommend boundary and never the escalation boundary | 3 |
| **D-A3-4** | **Citations are real, and that is free.** MedlinePlus + RxNav/RxNorm — public domain, no key, no registration — never generated content. The LOINC table is deliberately not a dependency. Where no vetted page exists, the assistant declares the gap | 1 |
| **D-A3-5** | **Exact lookup before semantic search.** LOINC and RxCUI joins for lab and medication education; vector search only for open-ended topics and note search, with per-patient filtering as a security control | 4 |
| **D-A3-6** | **Publication is deterministic**, and **refusals short-circuit before retrieval** — minimum necessary enforced by graph topology rather than by a downstream filter | 5 |
