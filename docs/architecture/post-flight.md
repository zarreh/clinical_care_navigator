# Post-flight

!!! info "In one paragraph, for a non-engineer"
    After the assistant writes a draft, three checks run on it: does anything it
    found in the record demand escalation regardless of the question; does every
    clinical statement have a source you can open; and does the draft do any of
    four things it is never allowed to do. Only the last one uses a language
    model, and it is only reached if the first two pass.

*Arrives in Phase 5.*

## 1 · `critical_value` — pure code

Every lab value the run retrieved is compared against
`data/lab_reference_ranges.csv`. A value in a **critical** band forces
escalation per the rule table, regardless of what the question was or what the
draft said. It cites the range row, so the basis is visible.

This is the check that makes *"what does my potassium of 6.9 mean?"* work.

## 2 · `citation_coverage` — pure code

Claims are classified as *clinical* or *navigational*. Every clinical claim must
carry at least one evidence reference resolving to a recorded tool call or an
education-source URL. Navigational claims ("you can message your care team") are
exempt, explicitly.

Below the floor, the run returns to `investigate` **once**, with the specific
uncited claims as feedback — not a generic retry.

## 3 · `scope_judge` — one model call

Four closed questions, each with a span:

- Does the draft **diagnose**?
- Does it **recommend a medication or dose change**?
- Does it **direct clinical action** beyond contacting a clinician?
- Does it **contradict the retrieved record**?

Four booleans with spans are testable. "Is this safe?" is not — a broad safety
judgement from a model is unmeasurable and unfalsifiable, and each of these four
maps to a specific rule a clinical owner can point at.

## Authority

Post-flight may escalate a run that pre-flight allowed. It may never relax a
pre-flight restriction. Asserted by test.
