# What it won't do

This list is the product, not a disclaimer appended to it.

## It will not

- **Diagnose.** Not a differential, not a "possible cause", not a probability.
- **Characterise urgency.** It does not decide how sick you are. It detects
  patterns on a *published* emergency-symptom list and directs you to care that
  can decide.
- **Recommend a medication, a dose, or a change to either.**
- **Direct clinical action** beyond "contact your clinician" or "seek emergency
  care".
- **Answer about anyone else's record.** Patient scoping is enforced in the tool
  layer, not requested of the model, and an attempt is recorded as a security
  event.
- **Invent an answer when it has no source.** If there is no vetted public page
  for a test or a medication, it says so and routes. It does not substitute a
  similar test and it does not generate content.
- **Write anything to a clinical record.** Every tool is read-only.

## It is not

A screener. A triage tool. A symptom checker. A medical device. A substitute for
professional care.

## Why the vocabulary matters

The system never says "your result is abnormal" — it says "your result is
outside the reference range your lab reported (x–y)". The first is an
interpretation. The second is a fact with its basis attached, which is what lets
you check it. See [Regulatory basis](../regulatory-basis.md).
