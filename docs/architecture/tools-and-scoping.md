# Tools and scoping

!!! info "In one paragraph, for a non-engineer"
    The assistant cannot decide which patient's record to read. That is fixed by
    code before any lookup runs, and if the assistant ever asks for someone
    else's data the attempt is overwritten *and written down*.

*Arrives in Phase 2.*

## Three controls at the executor, not in the prompt

**Allowlist.** A tool call naming a tool that is not registered is blocked and
recorded. The model cannot invent a capability.

**Patient scoping.** For every patient-scoped tool, the `patient_id` argument is
overwritten with the authenticated patient's id before the tool runs. The model's
value is discarded.

**Row caps.** Retrieval volume is capped per call. This is a cost control and a
minimum-necessary control at the same time.

## Scoping attempts are recorded

An overwrite emits a typed `SecurityEvent` that is persisted and shown in the
trace. Without it, a model that just tried to read another patient's chart
produces exactly the same audit trail as one that did not — which is the least
useful possible outcome for the single most interesting event the system can
observe.

## Scope is selected by the gate, not filtered afterwards

The tool registry the agent is bound to is chosen by the policy decision. A
refused or escalated question never reaches a patient tool at all, so no record
is read for a question that was always going to be declined.

## Vector search is scoped too

Note search filters by patient at the collection level. A note search that could
return another patient's note is the same class of defect as an unscoped SQL
query, and it gets the same test.
