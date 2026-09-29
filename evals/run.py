"""Layer 1 canonical regression runner (docs/PLAN.md §4.5).

Gates PR CI: exits non-zero if any of the 18 canonical runs doesn't match its
expected behaviour (docs/PLAN.md §4.5, §7 Phase 8).
"""

import sys

from evals.canonical import print_matrix, run_canonical_eval


def main() -> int:
    results, report = run_canonical_eval()
    print_matrix(results, report)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
