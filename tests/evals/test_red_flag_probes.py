"""The committed red-flag probe set matches its documented expectation (§6.3
chart 2). A probe with the wrong phrasing for its rule pattern is a test bug,
not a finding -- this is what catches that before it reaches the chart."""

from __future__ import annotations

from evals.red_flag_probes import run_probes


def test_every_probe_matches_its_documented_expectation() -> None:
    scored = run_probes()
    mismatches = [
        (probe.group, probe.category, probe.text)
        for probe, fired in scored
        if fired != probe.should_fire
    ]
    assert not mismatches, mismatches


def test_recall_on_red_flag_positives_is_complete() -> None:
    scored = run_probes()
    positives = [(p, fired) for p, fired in scored if p.group == "positive"]
    assert positives
    assert all(fired for _, fired in positives)
