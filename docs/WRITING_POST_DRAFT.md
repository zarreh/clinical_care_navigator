# Why a healthcare guardrail has to check the evidence, not just the question (draft — staged for `/writing`)

This is drafted content for the per-app post described in
`PORTFOLIO_PLAN_V3.md` §14 (`/writing`). It lives here, excluded from this
repo's own published docs site, because the shared portfolio site does not
exist yet in this workspace.

---

Most "safe" healthcare chatbot demos put a disclaimer in the system prompt,
add an intent classifier, and call the combination a guardrail. It's a
reasonable instinct, and it has an exact blind spot: it can only ever look at
the *question*. It has no way to catch the case where the question is
completely ordinary and the *data* is the emergency.

That case is real, and it's the one this project is built around.

## The case that breaks a question-only gate

Someone asks: *"What does my potassium of 6.9 mean?"* Read the question on
its own and it's the most benign kind of thing this assistant handles —
plain lab-education, the same shape as "what does my A1c mean". A gate that
only inspects the question will wave it through every time, and it should:
nothing in the sentence itself is dangerous.

The number is. A potassium of 6.9 mmol/L is a published critical value —
the kind of result a lab calls a clinician about immediately, not the kind
you explain calmly in a paragraph. A system that answers this question
correctly and *helpfully* — citing the right reference range, using calm
and clear language, doing everything a good lab-education assistant should
do — has still failed, because none of that changes what the number means.

## The fix: judge the evidence, not the question

The architecture here runs policy twice: once before the model
(`resolve_policy`, on the question) and once after it (`post_flight`, on the
retrieved evidence and the drafted answer). The second pass doesn't replay
the first — it has its own authority, and it can escalate a run the first
pass was happy to allow. It can never do the opposite: a restriction the
first pass imposed is a floor the second pass can raise but never lower.

Concretely, for potassium: `post_flight` runs a pure-code scan
(`guardrails/critical_values.py`) over every lab value the run actually
retrieved, independent of what the question was and independent of what the
draft says. If a value crosses a published critical threshold, the run is
forced to the emergency-care route — full stop, regardless of how
reassuring the drafted answer sounded a moment earlier.

## What this costs, and why it's worth it

The two cheapest checks run first — a critical-value scan (a table lookup,
free) and a citation-coverage check (also free) — and only the third check,
a model call that judges whether the draft diagnosed, changed a medication,
or contradicted the record, actually costs anything. A run that escalates on
a critical value never reaches that expensive check at all, which means the
most dangerous cases are also the cheapest to catch correctly. Safety here
isn't a flat tax on every request; it's ordered so the expensive judgement
only runs when the cheap ones didn't already have the answer.

The honest cost is architectural, not computational: you have to build two
independent decision points instead of one, and you have to resist the
temptation to let the second one just rubber-stamp the first. The payoff is
a system that can be wrong about a *question* and still be caught by what it
*found* — which is, I'd argue, the actual bar for something that reads a
medical record.
