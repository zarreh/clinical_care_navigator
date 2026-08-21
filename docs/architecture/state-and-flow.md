# State and flow

!!! info "In one paragraph, for a non-engineer"
    Each step of the system can only see the information it needs. The step that
    classifies your question, for example, never sees any of your clinical data
    at all.

*The real state model arrives in Phase 3; Phase 0 ships only a walking-skeleton
state that exists to prove the streaming path.*

## Narrow projections

Every node receives a read-only projection of state rather than the whole blob.

| Node | Sees |
|---|---|
| `classify_intent` | The question and the patient's literacy level. **No clinical content** |
| `investigate` | The policy decision, the tool scope, evidence gathered so far |
| `extract_claims` | The draft answer only |
| `post_flight` | Draft, evidence records, pre-flight decision. Not the raw message history |
| `publish` | The judged answer and the policy record |

`classify_intent` not seeing clinical content is a deliberate privacy property,
not an optimisation.

## Bounded loops

Both counted in state, both with a test asserting termination:

- `evidence_pass ≤ 1` — one repair pass for uncited claims
- `tool_calls ≤ max_tool_calls` — plus a token and wall-clock ceiling

On breach the run terminates with a conservative templated response and the
reason recorded. It never silently truncates a clinical answer.

## Streaming

The API bridges `astream_events` to Server-Sent Events, one event per node. The
node filter is `name == metadata["langgraph_node"]`, because conditional-edge
routing functions also emit `on_chain_end` carrying the *source* node in their
metadata under their own function name.

::: navigator.graph.state
