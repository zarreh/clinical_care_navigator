"""Acquire a synthetic patient population.

Downloads the published Synthea sample CSV export (Apache-2.0) and selects a
deterministic cohort from it. Nothing here is a real person and nothing here is
committed — `make data` rebuilds it from nothing (docs/PLAN.md §4.1).

Why download rather than run the generator: Synthea is a Java application, and
adding a JVM to the build to produce data that its authors already publish in a
fixed, versioned export buys nothing. The published export is the same tool's
output, and using it keeps the pipeline reproducible without a second toolchain.

Cohort selection is **deterministic rather than random**: patients are ranked by
how many of their laboratory observations carry a LOINC code the reference-range
table covers, ties broken by patient id. That is reproducible without a seed and
it biases the population toward analytes the education pipeline can actually
cite — the coverage steer the plan asks for in §4.2.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

SAMPLE_URL = (
    "https://synthetichealth.github.io/synthea-sample-data/downloads/latest/"
    "synthea_sample_data_csv_latest.zip"
)
USER_AGENT = "clinical-care-navigator-build/0.1 (synthetic data build; +https://github.com/zarreh)"

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
SYNTHEA_DIR = DATA_DIR / "synthea"
RANGES_CSV = DATA_DIR / "lab_reference_ranges.csv"

# Everything the portal schema needs. claims*, payers, devices, supplies and
# organizations are deliberately not extracted: nothing in this app reads them,
# and an unused copy of a record is a minimum-necessary problem (§3.3).
WANTED = (
    "patients.csv",
    "encounters.csv",
    "observations.csv",
    "medications.csv",
    "conditions.csv",
    "procedures.csv",
    "allergies.csv",
)

DEFAULT_COHORT_SIZE = 25


def download(url: str, destination: Path) -> Path:
    """Fetch `url` to `destination`, skipping the download if it is already there."""
    if destination.exists() and destination.stat().st_size > 0:
        size = destination.stat().st_size
        print(f"  cached  {destination.relative_to(DATA_DIR)} ({size:,} bytes)")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetch   {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - fixed https URL
        temporary = destination.with_suffix(destination.suffix + ".part")
        with temporary.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    temporary.replace(destination)
    print(f"  saved   {destination.relative_to(DATA_DIR)} ({destination.stat().st_size:,} bytes)")
    return destination


def extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        available = set(bundle.namelist())
        missing = [name for name in WANTED if name not in available]
        if missing:
            raise SystemExit(f"Synthea export is missing expected files: {missing}")
        for name in WANTED:
            target = destination / name
            with bundle.open(name) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            print(f"  extract {name} ({target.stat().st_size:,} bytes)")


def covered_loinc_codes() -> set[str]:
    with RANGES_CSV.open(encoding="utf-8") as handle:
        return {row["loinc_code"] for row in csv.DictReader(handle)}


def select_cohort(synthea_dir: Path, size: int) -> list[str]:
    """Rank patients by covered-analyte count, break ties by id, take `size`."""
    covered = covered_loinc_codes()
    scores: Counter[str] = Counter()

    with (synthea_dir / "observations.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["CATEGORY"] == "laboratory" and row["CODE"] in covered:
                scores[row["PATIENT"]] += 1

    with (synthea_dir / "patients.csv").open(encoding="utf-8", newline="") as handle:
        living_adults = [
            row["Id"]
            for row in csv.DictReader(handle)
            if not row["DEATHDATE"] and row["BIRTHDATE"] < "2008-01-01"
        ]

    ranked = sorted(living_adults, key=lambda pid: (-scores[pid], pid))
    chosen = [pid for pid in ranked if scores[pid] > 0][:size]
    if len(chosen) < size:
        raise SystemExit(
            f"Only {len(chosen)} patients have covered lab results; wanted {size}. "
            "Widen data/lab_reference_ranges.csv or lower --cohort-size."
        )
    return chosen


def write_cohort(cohort: list[str], destination: Path) -> None:
    destination.write_text("\n".join(cohort) + "\n", encoding="utf-8")
    print(f"  cohort  {len(cohort)} patients -> {destination.relative_to(DATA_DIR)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-size", type=int, default=DEFAULT_COHORT_SIZE)
    parser.add_argument("--url", default=SAMPLE_URL)
    args = parser.parse_args(argv)

    print("fetch_synthea")
    archive = download(args.url, RAW_DIR / "synthea_sample_data_csv.zip")
    extract(archive, SYNTHEA_DIR)
    cohort = select_cohort(SYNTHEA_DIR, args.cohort_size)
    write_cohort(cohort, SYNTHEA_DIR / "cohort.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
