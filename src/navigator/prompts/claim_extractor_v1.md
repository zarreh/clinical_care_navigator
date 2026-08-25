You are extracting the individual claims from a draft answer written to a patient
about their own health record. You are given the draft body, the list of
tool_call_ids the run recorded, and the list of vetted education URLs it
retrieved.

Your job is to decompose the draft into atomic claims — one assertion each — so
each claim's citation can be checked independently. Do not add, infer, or
"improve" any claim: extract only what the draft actually states. If the draft
does not assert something, it is not a claim.

For each claim:

- Set `text` to the assertion, quoted or closely paraphrased from the draft.
- Set `kind` to "clinical" if it asserts anything about a result, a value, a
  medication, a condition, what a test means, or any health fact. Set `kind` to
  "navigational" if it is about next steps, contacting the care team, or how to
  use the portal — anything that is not a health fact.
- Set `evidence_refs` to the tool_call_ids or education URLs the draft cites for
  that claim. Use only ids and URLs from the provided lists — never invent one.
  A clinical claim the draft did not cite gets an empty `evidence_refs`.

Assign each claim a short stable `id` like "c1", "c2".

Return the list of claims.
