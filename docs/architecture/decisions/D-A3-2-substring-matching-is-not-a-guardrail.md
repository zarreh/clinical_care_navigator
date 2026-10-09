# D-A3-2: Substring matching is not a guardrail

**Status:** Accepted, implemented (`guardrails/rule_engine.py`,
`graph/nodes/classify_intent.py`, `graph/nodes/resolve_policy.py`, Phase 3).

## Context

The source notebook's safety gate was a bare keyword match: any occurrence of
a red-flag term escalated the run, with no way to tell "I have chest pain"
from "no chest pain" or from "my discharge note says to watch for chest pain".
A gate that cannot make that distinction is not a safety control — it is a
trigger-happy filter that a patient learns to route around, or a system a
clinical owner cannot trust to answer anything at all (over-refusal, §8).

## Decision

Pre-flight is two layers, combined by code with fixed severity precedence
(`schemas/preflight.py::ACTION_SEVERITY`), and both directions of error are
measured:

1. `screen_rules` — a deterministic pattern layer with a negation/attribution
   context check (`RuleEngine.screen`). A red-flag term under negation ("no
   chest pain") or inside an attribution to the record ("my discharge note
   says...") is recorded as suppressed and does not fire.
2. `classify_intent` — one structured LLM call that catches what the lexicon
   defeats — a metaphor ("like an elephant sitting on my chest", canonical
   case 11) that contains no red-flag words at all.

`resolve_policy` combines them: the more restrictive action wins, and whether
the two layers agreed is recorded (`layer_agreement`) rather than smoothed
over. `tests/graph/test_resolve_policy.py::test_case11_metaphor_emergency_via_classifier`
and `::test_case12_attributed_red_flag_is_ordinary_answer` assert both
directions directly, and `evals/red_flag_probes.py` scores the screen layer
alone against a committed probe set — including probes it is *expected* to
miss, so the miss is documented rather than discovered later.

## Consequences

- Neither layer alone is the guardrail; the guardrail is the combination plus
  the recorded disagreement rate, which is itself a published number
  (`docs/evidence/evaluation.md`).
- The screen's blind spot (metaphor) is named and probed on purpose
  (`evals/red_flag_probes.py`'s `metaphor` group), not discovered by a user.
- Over-refusal has a concrete lever: the negation/attribution check, which is
  what makes case 12 an ordinary answer rather than an escalation.
