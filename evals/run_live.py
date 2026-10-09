"""CLI entry point for `make eval-live` (docs/PLAN.md §7 Phase 8).

Runs the Layer 1 canonical set against the live model and prints the pass/fail matrix.
`make eval` is the key-free oracle gate in `evals/run.py`; this one needs a key and spends tokens.
The run/print/gate shell is `zarreh_agentkit.evals.run_eval_cli` (shared
with A2); the scenarios, fixtures and checks stay local, per HARVEST #14.

Requires `NAVIGATOR_OPENAI_API_KEY` (and, for traced runs, the LangSmith
vars) — this suite drives the real compiled graph with the live model; see
evals/live.py for why, unlike A2, no oracle stands in for it.
"""

from __future__ import annotations

import sys

from zarreh_agentkit.evals import run_eval_cli

from evals.live import outcomes, print_report, run_canonical_eval


def main() -> int:
    return run_eval_cli(run_canonical_eval, print_report, outcomes)


if __name__ == "__main__":
    sys.exit(main())
