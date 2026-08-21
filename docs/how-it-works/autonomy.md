# Autonomy — what the knob does, and what it costs

!!! info "In one paragraph, for a non-engineer"
    A clinical team can decide how much this assistant answers on its own versus
    how much it holds for a human to review. That setting is visible, it is
    recorded on every answer, and its effect is measured. It cannot be used to
    switch off emergency handling.

## Bands are a property of the question

Every question is classified into one of three bands:

| Band | Examples |
|---|---|
| `inform` | Lab and medication education, looking up your own record |
| `recommend` | Anything decision-adjacent — interactions, "is this normal for me" |
| `escalate` | Red-flag symptoms, dosing changes, crisis |

## The setting moves one boundary only

| Setting | Effect | Consequence |
|---|---|---|
| `L1 Conservative` | Some `inform` questions are treated as `recommend` | Most clinician review, least answered autonomously |
| `L2 Balanced` *(default)* | Bands as classified | — |
| `L3 Permissive` | Some `recommend` questions are answered with education plus an explicit referral | Least review, higher over-answer risk |

**The escalation boundary does not move.** Red flags escalate at every level and
there is no setting that turns that off. That constraint is the reason the knob
is safe to expose at all, and there is a test asserting it.

Showing that the knob exists *and what it costs* is the argument. Claiming a safe
default without showing the trade is not.
