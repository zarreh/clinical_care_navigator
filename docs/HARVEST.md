# Harvest log — patterns copied from A2

`PORTFOLIO_PLAN_V3.md` §8 and `docs/PLAN.md` §0.3: no shared package is extracted
from a single implementation. A3 is the second implementation, so extraction
becomes *possible* — but it happens as a discrete step **after** A3 ships, driven
by this list.

For each entry: what was copied, what had to change, and whether the difference
is **essential** (the two apps genuinely need to differ) or **incidental** (they
differ only because they were written separately). Incidental differences are
what the shared package removes; essential ones are what its API has to
accommodate.

| # | Pattern | Source in A2 | Change in A3 | Difference |
|---|---|---|---|---|
| 1 | `Settings` + `get_settings` via `pydantic-settings` | `settings.py` | Different fields, `NAVIGATOR_` prefix | Incidental — candidate for an X2 base class |
| 2 | `configure_logging` / `get_logger` | `observability.py` | Identical | Incidental — extract verbatim |
| 3 | `MaxBodySizeMiddleware` | `api/middleware.py` | Identical apart from the docstring reference | Incidental — extract verbatim |
| 4 | Per-route `Limiter` rather than `SlowAPIMiddleware` | `api/rate_limit.py` | Identical | Incidental — extract verbatim, including the `include_router` caveat |
| 5 | Multi-stage Dockerfile, non-root, `HEALTHCHECK` | `Dockerfile` | Package name only | Incidental |
| 6 | CI/CD split, `mkdocs build --strict` gating PRs | `.github/workflows/` | Package name only | Incidental |
| 7 | MkDocs + Material config and plugin set | `mkdocs.yml` | Different nav | Incidental — this is X5 `zarreh-docs-theme` |
| 8 | SSE bridge over `astream_events` | `api/streaming.py` | A3 filters `name == metadata["langgraph_node"]` from the start | Incidental — A3's filter is the correct one |
| 9 | `builder.py` as the only wiring file; node filename == node name == span name | `graph/builder.py` | Same convention | **Essential convention**, not shared code |
| 10 | Deterministic publication (A2 D-A2-1 → A3 D-A3-6) | `graph/nodes/publish.py` | Same property, different payload | **Essential** — second occurrence; promote to an X2 convention |
| 11 | Claim-level grounding schemas (`Claim` / `ClaimAnalysis`) | `schemas/` | A3 adds `kind: clinical\|navigational` | **Essential** — the shared schema needs the claim-kind axis |
| 12 | Budget guardrail | `graph/budget.py` | A3 terminates with a *clinical* conservative template | **Essential** — the ceiling is shared, the breach response is not |
| 13 | Narrow state projections | `graph/state.py` | Same idea, different views | **Essential convention** — third occurrence overall (UT wk11, UT wk13, A2) |
| 14 | Two evaluation layers with metrics fixed before labelling | `evals/` | Different metrics | **Essential** — the runner is shareable, the metric set is not |
| 15 | `plot_style.mplstyle` and the light/dark `_save` helper | `docs/generate_plots.py`, `docs/assets/` | Copied verbatim, then **made deterministic**: `metadata={"Date": None}` plus a pinned `svg.hashsalt` | **Essential fix** — A2's charts embed a timestamp, so its own no-drift rule cannot run. The shared version should carry A3's determinism |
| 16 | Store repository layer with typed row models | `store/fact_store.py`, `store/models.py` | A3 adds a **row cap inside the store** and admits no unscoped clinical read | **Essential** — the cap is a minimum-necessary control in A3 and a cost control in A2 |
| 17 | Build scripts as `data/` modules run by `make data` | `data/build_store.py` | Same shape; A3 adds fail-loud provenance checks | Incidental — the pattern is shared, the checks are domain-specific |

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
