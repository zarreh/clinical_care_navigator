# API reference

Generated from source by `mkdocstrings` — never hand-written, so it cannot go
stale.

Interactive OpenAPI documentation is served by the running application at
`/docs`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness |
| `POST` | `/conversations/stream` | Ask a question; streams the run node by node over SSE |

Every response carries the synthetic-data and not-a-medical-device statement.
Endpoints are rate limited per client and request bodies are capped at the ASGI
layer.

## Settings

::: navigator.settings

## Streaming

::: navigator.api.streaming

## Graph

::: navigator.graph.builder
