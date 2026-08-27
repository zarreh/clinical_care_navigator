"""CLI entry point for `make eval` (docs/PLAN.md §7 Phase 8).

Runs the Layer 1 canonical regression set and prints the pass/fail matrix.
The run/print/gate shell is `zarreh_agentkit.evals.run_eval_cli` (shared
with A2); the scenarios, fixtures and checks stay local, per HARVEST #14.

Requires `NAVIGATOR_OPENAI_API_KEY` (and, for traced runs, the LangSmith
vars) — this suite drives the real compiled graph with the live model; see
evals/canonical.py for why, unlike A2, no oracle stands in for it.
"""

from __future__ import annotations

import sys

from zarreh_agentkit.evals import run_eval_cli

from evals.canonical import outcomes, print_report, run_canonical_eval


def main() -> int:
    return run_eval_cli(run_canonical_eval, print_report, outcomes)


if __name__ == "__main__":
    sys.exit(main())
