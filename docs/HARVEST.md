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

## Frontend components

Filled in during Phase 7. Components stay local; each is logged here as an
extraction candidate for X3 `@zarreh/agent-ui`.

| # | Component | Notes |
|---|---|---|
| — | *pending Phase 7* | |
