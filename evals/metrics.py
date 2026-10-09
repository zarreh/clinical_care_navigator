"""Metric definitions (docs/PLAN.md §8).

Layer 1 (`evals/canonical.py`) uses only `MetricsReport` -- pass/fail plus cost
and latency percentiles over n=18 oracle-scored runs. It is a regression smoke
test, not a measurement (§4.5), so it never computes a rate metric like
under-refusal or red-flag recall: at this sample size and with a scripted
oracle standing in for judgement, a published rate would imply a precision the
sample cannot support (§4.5, §8). `wilson_interval` exists for Layer 2, once a
real labelled sample and pinned model versions exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    """One canonical case's run, and whether it matched its expectation."""

    run_id: str
    case_id: str
    ok: bool
    detail: str
    cost_usd: float
    latency_seconds: float


@dataclass(frozen=True)
class MetricsReport:
    n: int
    pass_rate: float
    cost_per_run_usd: float
    latency_p50_seconds: float
    latency_p95_seconds: float


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(p * (len(ordered) - 1)))
    return ordered[index]


def compute_metrics(results: list[EvalResult]) -> MetricsReport:
    n = len(results)
    if n == 0:
        return MetricsReport(
            n=0,
            pass_rate=0.0,
            cost_per_run_usd=0.0,
            latency_p50_seconds=0.0,
            latency_p95_seconds=0.0,
        )
    passed = sum(1 for r in results if r.ok)
    costs = [r.cost_usd for r in results]
    latencies = [r.latency_seconds for r in results]
    return MetricsReport(
        n=n,
        pass_rate=passed / n,
        cost_per_run_usd=sum(costs) / n,
        latency_p50_seconds=_percentile(latencies, 0.5),
        latency_p95_seconds=_percentile(latencies, 0.95),
    )


def wilson_interval(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion (Layer 2, §4.5).

    Preferred over the naive normal-approximation interval at the small sample
    sizes Layer 2 starts at (~150): it never produces a bound outside [0, 1],
    and it is the standard choice for reporting a rate off a sample that small.
    """
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * n)) / n)
    return (max(0.0, (center - margin) / denom), min(1.0, (center + margin) / denom))
