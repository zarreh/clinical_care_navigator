# The policy engine

!!! info "In one paragraph, for a non-engineer"
    Before the assistant looks at anything, the question passes two checks that
    run at the same time: a fast list-based one and a slower language-model one.
    A piece of ordinary code combines their verdicts, always taking the more
    cautious of the two, and records when they disagreed.

*Arrives in Phase 3.*

## Why not just match keywords

The obvious approach — check whether a red-flag phrase appears in the text —
fails in both directions, and both failures are one line long:

| Input | Keyword matching | Correct |
|---|---|---|
| *"I feel like an elephant is sitting on my chest"* | no match → answer | emergency |
| *"my discharge note says to watch for chest pain"* | match → emergency | ordinary answer |
| *"is it okay to come off my metformin"* | no match → answer | out of scope |

Over-refusal is the failure mode that gets safety systems switched off, and it
is the one nobody measures.

## The three layers

| Layer | Kind | Catches | Misses |
|---|---|---|---|
| `screen_rules` | Compiled patterns, word-boundary aware, with a negation and attribution check | Explicit red-flag and dosing language. Fast, free, fully auditable | Paraphrase, metaphor, other languages |
| `classify_intent` | One structured model call | Metaphor, paraphrase, indirect phrasing | Adversarial phrasing aimed at it |
| `resolve_policy` | Code | Combines by fixed severity precedence, applies the autonomy boundary, selects the tool scope | — |

The negation and attribution check is what makes the second row of the table
above work: a red-flag term quoted *from the patient's own record*, or under a
negation, is attributed rather than asserted.

Precedence is fixed:
`direct_to_emergency_care > crisis > out_of_scope > clinician_review > allow`.
Where the layers disagree the more restrictive wins, and the disagreement is
recorded — the disagreement rate is itself a published number.
