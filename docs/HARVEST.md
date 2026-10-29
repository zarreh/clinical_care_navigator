# Harvest log — patterns copied from A2

`PORTFOLIO_PLAN_V3.md` §8 and `docs/PLAN.md` §0.3: no shared package is extracted
from a single implementation. A3 is the second implementation, so extraction
becomes *possible* — but it happens as a discrete step **after** A3 ships, driven
by this list.

**Update (2026-08-27):** that discrete step happened, as `zarreh-agentkit`
v0.2.0, once A12 existed too as a third real instance. Rows 1–4 and 12 are
now harvested (see the kit's `settings`, `observability.build_tracing_callbacks`,
`api.middleware`, `api.rate_limit`, `guardrails.budget`); row 14's *shell*
(`evals.run_eval_cli`) is harvested, but the metric set stays local, exactly
as this row already said it would. Row 2's "incidental, extract verbatim"
call was corrected in the harvest: `get_logger` extracts cleanly, but
`configure_logging` does not — this service's PHI-redactor hook is an
essential difference the kit has no reason to carry for a single consumer,
so `configure_logging` stays local. Rows 5–11, 13, 15–17 are unaffected by
this pass (Docker/CI/docs/store-layer patterns, or conventions rather than
code) and remain open harvest candidates.

For each entry: what was copied, what had to change, and whether the difference
is **essential** (the two apps genuinely need to differ) or **incidental** (they
differ only because they were written separately). Incidental differences are
what the shared package removes; essential ones are what its API has to
accommodate.

| # | Pattern | Source in A2 | Change in A3 | Difference |
|---|---|---|---|---|
| 1 | ✅ `Settings` + `get_settings` via `pydantic-settings` | `settings.py` | Different fields, `NAVIGATOR_` prefix | Incidental — harvested as `zarreh_agentkit.settings.AgentSettings` |
| 2 | ✅ `configure_logging` / `get_logger` | `observability.py` | Identical *only for `get_logger`* | `get_logger` harvested verbatim; `configure_logging` stayed local — its PHI-redactor hook is essential, not incidental as first thought |
| 3 | ✅ `MaxBodySizeMiddleware` | `api/middleware.py` | Identical apart from the docstring reference | Incidental — harvested as `zarreh_agentkit.api.middleware` |
| 4 | ✅ Per-route `Limiter` rather than `SlowAPIMiddleware` | `api/rate_limit.py` | Identical | Incidental — harvested as `zarreh_agentkit.api.rate_limit`, including the `include_router` caveat |
| 5 | Multi-stage Dockerfile, non-root, `HEALTHCHECK` | `Dockerfile` | Package name only | Incidental |
| 6 | CI/CD split, `mkdocs build --strict` gating PRs | `.github/workflows/` | Package name only | Incidental |
| 7 | MkDocs + Material config and plugin set | `mkdocs.yml` | Different nav | Incidental — this is X5 `zarreh-docs-theme` |
| 8 | SSE bridge over `astream_events` | `api/streaming.py` | A3 filters `name == metadata["langgraph_node"]` from the start | Incidental — A3's filter is the correct one |
| 9 | `builder.py` as the only wiring file; node filename == node name == span name | `graph/builder.py` | Same convention | **Essential convention**, not shared code |
| 10 | Deterministic publication (A2 D-A2-1 → A3 D-A3-6) | `graph/nodes/publish.py` | Same property, different payload | **Essential** — second occurrence; promote to an X2 convention |
| 11 | Claim-level grounding schemas (`Claim` / `ClaimAnalysis`) | `schemas/` | A3 adds `kind: clinical\|navigational` | **Essential** — the shared schema needs the claim-kind axis |
| 12 | ✅ Budget guardrail | `graph/budget.py` | A3 terminates with a *clinical* conservative template | **Essential** — the ceiling is now `zarreh_agentkit.guardrails.budget`, the breach response stayed local as predicted |
| 13 | Narrow state projections | `graph/state.py` | Same idea, different views | **Essential convention** — third occurrence overall (UT wk11, UT wk13, A2) |
| 14 | ✅ Two evaluation layers with metrics fixed before labelling | `evals/` | Different metrics, and A3's Layer 1 needs the live model, not an oracle | **Essential** — the run/print/gate shell is now `zarreh_agentkit.evals.run_eval_cli`, the metric set stayed local as predicted |
| 15 | `plot_style.mplstyle` and the light/dark `_save` helper | `docs/generate_plots.py`, `docs/assets/` | Copied verbatim, then **made deterministic**: `metadata={"Date": None}` plus a pinned `svg.hashsalt` | **Essential fix** — A2's charts embed a timestamp, so its own no-drift rule cannot run. The shared version should carry A3's determinism |
| 16 | Store repository layer with typed row models | `store/fact_store.py`, `store/models.py` | A3 adds a **row cap inside the store** and admits no unscoped clinical read | **Essential** — the cap is a minimum-necessary control in A3 and a cost control in A2 |
| 17 | Build scripts as `data/` modules run by `make data` | `data/build_store.py` | Same shape; A3 adds fail-loud provenance checks | Incidental — the pattern is shared, the checks are domain-specific |
| 18 | Deterministic oracle standing in for a live LLM at Layer 1 | `evals/oracle.py` | A3's oracle needs two case-specific pieces (a fixed classification, a fixed tool-call script) instead of one (A2's investigator); the answer writer, claim extractor and scope judge are generic in both | **Essential** — second occurrence; the "why an oracle, not recorded responses" framing and the record_responses.py replacement plan are identical in both repos |
| 19 | Chart-drift check enforced by a real pytest test, not a Makefile diff step | `tests/docs/test_chart_determinism.py` | A2's docstring claims the CI check but never wires it; A3 has an actual test (byte-digest before/after regeneration, backed up and restored) | **Essential fix** — the shared version should be A3's test, not A2's unenforced claim |
| 20 | Material announcement bar via `theme.custom_dir` override | `overrides/main.html`, `mkdocs.yml` | New in A3 (A2 has no announcement bar) | First occurrence — logged as an X5 `zarreh-docs-theme` candidate once a second app needs one |

## Extraction status (2026-10-28)

A3 now consumes `zarreh-agentkit` v0.5.0. What moved, and what deliberately did not:

| # | Pattern | Status |
|---|---|---|
| 1 | `Settings` base | **Extracted** — `Settings(AgentSettings)`; A3 keeps its own `env_prefix`, fields, and a tighter `max_request_body_bytes` |
| 3 | `MaxBodySizeMiddleware` | **Extracted** — `api/middleware.py` is a re-export |
| 4 | Per-route `Limiter` | **Extracted** — `api/rate_limit.py` builds on `build_limiter` / `default_rate_limit` |
| 12 | Budget guardrail | **Extracted** — ceiling from the library; A3 keeps its own `DEFAULT_BUDGET` (12 calls / 90s) and its conservative-template breach response |
| — | Cost accounting | **Extracted** (v0.3.0) — `cost_tracking.py` is a re-export. The library now carries the three fixes A3 needed: node tag read from the start event, `usage_metadata` fallback for structured output, dated model names priced by family. `CostEntry` is the library's |
| — | Tracing callbacks | **Extracted** (v0.3.0) — the library binds the tracer to a `langsmith.Client` carrying the key, so A3's private copy (which existed to avoid a 401) is gone |
| 2 | `configure_logging` | **Extracted** (v0.2.1) — `observability.configure_logging` wraps the library's, passing the PHI redactor through `extra_processors` so it still runs immediately before the renderer |
| 8 | SSE bridge | **Extracted** (v0.2.1) — `stream_graph_events` is the library's, with the `name == langgraph_node` filter |
| — | Run store events/costs | **Extracted** (v0.4.0) — `RunStore` subclasses `RunEventLog(table_prefix="conversation")`, so the table names are unchanged; the `conversations` table, follow-up migration and review columns stay local |
| — | Replay-then-tail SSE | **Extracted** (v0.4.0) — `stream_conversation_events` is `replay_and_tail`; the `max_wait_seconds` bound is applied in its `poll_end` |
| — | Prompt loader, `/healthz` | **Extracted** (v0.4.0) |
| — | Node-step loop | **Partly extracted** (v0.4.0) — the executor uses `iter_node_outputs`/`json_default`. It does not use `execute_run`: after streaming it awaits `aget_state` to detect a held review, and `execute_run`'s finaliser is synchronous |
| — | Injection scan | **Extracted** (v0.5.0) — `scan_for_injection` is `first_matching_rule(...) is not None` over the shared catalogue |
| 16 | Store row cap | **Kept local** — domain-specific (minimum-necessary control) |
| — | PHI redaction (`PhiRedactor`) | **Kept local** — still the only redaction primitive of its shape (the library's README lists it as deferred) |
| — | Retrieval (`note_search`) | **Kept local** — a raw Qdrant client with a mandatory per-patient filter; it did not share a core with the other Qdrant consumer |
| — | Claim extraction / citation coverage | **Kept local** — A3 verifies coverage deterministically against recorded evidence ids, not by an LLM grounding judge, so the library's grounding aggregation does not apply |

## Frontend components

Filled in during Phase 7. Components stay local; each is logged here as an
extraction candidate for X3 `@zarreh/agent-ui`.

| # | Component | Notes |
|---|---|---|
| F1 | `PrototypeBanner` | Synthetic-data / not-a-medical-device banner rendered in the root layout on every page. Second occurrence (A2 had the same shape) — **essential**, promote to the X3 `@zarreh/agent-ui` shell |
| F2 | `RunConsole` | Orchestrates create → SSE stream → fetch, with loading/streaming/success/empty/error phases. Same state machine as A2's `RunConsole`; the domain payload differs — **essential convention**, shareable with a typed answer generic |
| F3 | `TraceTimeline` | Node-by-node step list keyed on `node filename == node name == span name` (HARVEST #9). Labels are domain-specific; the component is not — **essential** |
| F4 | `EvidencePanel` | Renders the `PatientAnswer`: disposition badge (pending ≠ approved), reading level, autonomy, citations as clickable links, clinical claims. Domain-specific rendering; the panel shell is reusable — incidental |
| F5 | `GuardrailStrip` | States which post-flight outcome fired (published / escalated / templated) and the claim coverage that drove it. A3 analogue of A2's `ValidatorStrip` — **essential**, second occurrence of the guardrail-status strip |
| F6 | `CostMeter` | Per-node cost table + total; unknown model prices to zero. Copied near-verbatim from A2 — **essential**, promote to X3 |
| F7 | `HITLDrawer` | Reviewer queue: list held drafts, approve/edit/decline, refresh. New in A3 (A2 had no HITL surface) — extraction candidate once a second occurrence appears |
| F8 | `lib/api.ts` + `lib/schemas.ts` | Typed API client over `openapi-typescript` types + Zod validation of the opaque answer payload at the SSE/HTTP boundary. Same pattern as A2 — **essential convention** |
| F9 | Playwright smoke + screenshot reuse | One set of network mocks drives both the smoke test and `make docs-screenshots`, so screenshots cannot drift from tested behaviour. Copied from A2 — **essential convention** |
