# API reference

Generated from source by `mkdocstrings` — never hand-written, so it cannot go
stale.

Interactive OpenAPI documentation is served by the running application at
`/docs`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness |
| `POST` | `/conversations` | Start a run (`202` with its id); the graph runs in the background. Pass `follow_up_to` (the latest run of a conversation) to ask a follow-up in the same conversation and patient |
| `GET` | `/conversations/{id}` | The durable record: status, answer, per-node cost |
| `GET` | `/conversations/{id}/thread` | Every turn of the conversation this run belongs to, oldest first |
| `GET` | `/conversations/{id}/events` | SSE: replays every stored step, then tails the run to completion |
| `GET` | `/personas` | The demonstration patients a visitor can ask as (a demo selector, not a login) |
| `GET` | `/reviews` | Drafts held for a clinician |
| `POST` | `/reviews/{id}/decision` | Approve, edit or decline; resumes the paused run from its checkpoint |
| `POST` | `/conversations/stream` | Phase 0 walking-skeleton stream, kept as the streaming proof |

Every response carries the synthetic-data and not-a-medical-device statement.
Endpoints are rate limited per client IP and per route: routes that start or
resume a model run share a strict ceiling (10/minute by default), reads and the
event stream a generous one (120/minute). A limited request gets `429`. Request
bodies are capped at the ASGI layer. `POST /conversations` only answers as one of the personas from `GET /personas`; any other `patient_id` gets a `404`. Errors carry a human-readable `detail`
(for example `404` for an unknown `patient_id`, `409` when a review was already
decided), which the frontend shows as-is.

## Settings

::: navigator.settings

## Streaming

::: navigator.api.streaming

## Graph

::: navigator.graph.builder
