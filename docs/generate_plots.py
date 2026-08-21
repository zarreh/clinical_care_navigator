"""Generate every chart in `docs/assets/` from real data.

Invoked by `make docs-assets`. CI fails if regenerating produces a diff against
what is committed, so a chart can never drift from the data it describes
(PORTFOLIO_PLAN_V3.md §9.4) — which is only possible if the input is
deterministic and available offline.

That is why these render from the **committed fixture stores** rather than from
`data/records.db`: the full population is rebuilt by `make data` and is
deliberately not committed (docs/PLAN.md §4.1), so a chart drawn from it could
not be regenerated in CI. Every chart states its *n* on the figure, and the
docs page says which population it describes. A chart that quietly implied a
larger sample than it had would be the same failure as an eval metric published
without its sample size (§8).

Phase 1 produces chart 8 (record-store profile, with education-source coverage).
Charts 1–7 need eval output and arrive in Phase 8.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from tests.fixtures import SEED_FILE, build_fixture_stores  # noqa: E402

ASSETS_DIR = Path(__file__).parent / "assets"
STYLE_PATH = ASSETS_DIR / "plot_style.mplstyle"

IN_RANGE = "#059669"
OUT_OF_RANGE = "#d97706"
CRITICAL = "#dc2626"
COVERED = "#2563eb"
GAP = "#dc2626"


def _save(fig: plt.Figure, name: str) -> None:
    for theme, colors in (
        ("light", {"fig": "white", "text": "#111827"}),
        ("dark", {"fig": "#0d1117", "text": "#e5e7eb"}),
    ):
        fig.patch.set_facecolor(colors["fig"])
        for ax in fig.axes:
            ax.set_facecolor(colors["fig"])
            ax.tick_params(colors=colors["text"])
            ax.xaxis.label.set_color(colors["text"])
            ax.yaxis.label.set_color(colors["text"])
            ax.title.set_color(colors["text"])
            for spine in ax.spines.values():
                spine.set_color(colors["text"])
            legend = ax.get_legend()
            if legend is not None:
                for text in legend.get_texts():
                    text.set_color(colors["text"])
        # metadata={"Date": None} strips the creation timestamp matplotlib would
        # otherwise embed. Together with the fixed svg.hashsalt below it makes the
        # output byte-identical across runs, which is what turns "CI fails on chart
        # drift" from an intention into a check that can actually run.
        fig.savefig(
            ASSETS_DIR / f"{name}-{theme}.svg",
            facecolor=colors["fig"],
            metadata={"Date": None},
        )
    plt.close(fig)


def _coverage_summary() -> dict[str, dict[str, float]]:
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    summary = seed.get("coverage_summary")
    if not summary:
        raise SystemExit(
            "tests/fixtures/seed.json has no coverage_summary. Run `make data` then "
            "`uv run python -m tests.fixtures.make_seed`."
        )
    return dict(summary)


def _band(value: float, row: tuple[object, ...]) -> str:
    reference_low, reference_high, critical_low, critical_high = row
    if critical_low is not None and value <= float(critical_low):
        return "critical"
    if critical_high is not None and value >= float(critical_high):
        return "critical"
    if reference_low is not None and value < float(reference_low):
        return "out_of_range"
    if reference_high is not None and value > float(reference_high):
        return "out_of_range"
    return "in_range"


def record_store_profile(records: sqlite3.Connection, education: sqlite3.Connection) -> None:
    """Chart 8: where the population's values sit, and what can be cited about them.

    Two panels because the page has to answer two different questions. The left
    one says whether the demo population contains anything worth escalating —
    a store of uniformly normal values would make the guardrail look good for
    the wrong reason. The right one says how much of it the system can actually
    cite, gaps included, because a coverage figure that hides its gaps is the
    metric equivalent of an uncited claim.
    """
    ranges = {
        str(row[0]): row[1:]
        for row in records.execute(
            "SELECT loinc_code, reference_low, reference_high, critical_low, critical_high "
            "FROM reference_ranges"
        )
    }
    rows = records.execute(
        "SELECT loinc_code, description, value_number FROM observations "
        "WHERE category = 'laboratory' AND value_number IS NOT NULL"
    ).fetchall()

    counts: dict[str, dict[str, int]] = {}
    labels: dict[str, str] = {}
    for loinc_code, description, value in rows:
        code = str(loinc_code)
        if code not in ranges:
            continue
        band = _band(float(value), ranges[code])
        counts.setdefault(code, {"in_range": 0, "out_of_range": 0, "critical": 0})[band] += 1
        labels[code] = str(description).split("[")[0].strip()[:24]

    ordered = sorted(counts.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:10]
    ordered.reverse()
    names = [f"{labels[code]}" for code, _ in ordered]
    in_range = [values["in_range"] for _, values in ordered]
    out_of_range = [values["out_of_range"] for _, values in ordered]
    critical = [values["critical"] for _, values in ordered]
    total_values = sum(in_range) + sum(out_of_range) + sum(critical)

    # Coverage describes the whole build, not these two patients: it is a
    # property of the education pipeline. The committed seed carries the build's
    # numbers so the panel states a real figure and still regenerates offline.
    coverage = _coverage_summary()
    covered_labs = int(coverage["labs"]["covered"])
    gap_labs = int(coverage["labs"]["gaps"])
    covered_meds = int(coverage["medications"]["covered"])
    gap_meds = int(coverage["medications"]["gaps"])

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 5))

    left.barh(names, in_range, color=IN_RANGE, label="Within reference band")
    left.barh(
        names, out_of_range, left=in_range, color=OUT_OF_RANGE, label="Outside reference band"
    )
    left.barh(
        names,
        critical,
        left=[a + b for a, b in zip(in_range, out_of_range, strict=True)],
        color=CRITICAL,
        label="Critical band",
    )
    left.set_title(f"Lab values by band (n={total_values} results)")
    left.set_xlabel("Results")
    left.legend(fontsize=8, loc="lower right")

    categories = ["Lab analytes", "Medications"]
    covered = [covered_labs, covered_meds]
    gaps = [gap_labs, gap_meds]
    right.bar(categories, covered, color=COVERED, label="Citable page")
    right.bar(categories, gaps, bottom=covered, color=GAP, label="Declared gap")
    for index, (cov, gap) in enumerate(zip(covered, gaps, strict=True)):
        total = cov + gap
        share = f"{cov / total:.0%}" if total else "n/a"
        right.text(index, total, f" {share} covered", ha="center", va="bottom", fontsize=9)
    right.set_title(
        f"Education-source coverage — full build "
        f"(n={covered_labs + gap_labs + covered_meds + gap_meds} codes)"
    )
    right.set_ylabel("Distinct codes")
    right.set_ylim(0, max(sum(pair) for pair in zip(covered, gaps, strict=True)) * 1.25 + 1)
    right.legend(fontsize=8, loc="upper right")

    fig.suptitle("Record-store profile — committed fixture population", fontweight="bold")
    fig.tight_layout()
    _save(fig, "record-store-profile")


def main() -> int:
    matplotlib.rcParams["svg.hashsalt"] = "clinical-care-navigator"
    plt.style.use(STYLE_PATH)
    with tempfile.TemporaryDirectory() as workspace:
        stores = build_fixture_stores(Path(workspace))
        records = sqlite3.connect(stores.records_db)
        education = sqlite3.connect(stores.education_db)
        try:
            record_store_profile(records, education)
        finally:
            records.close()
            education.close()
    print(f"wrote charts to {ASSETS_DIR.relative_to(Path(__file__).parents[1])}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
