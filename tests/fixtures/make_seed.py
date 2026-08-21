"""Extract a tiny, committed seed from the built stores.

Run by hand after a data rebuild, not by CI:

    uv run python -m tests.fixtures.make_seed

Why a JSON seed rather than a committed SQLite file: the tests need to run
offline and free (docs/PLAN.md §4.6), but a binary in git is opaque to review,
and this seed contains synthetic clinical rows that a reviewer should be able to
read. JSON keeps the diff legible and keeps the schema owned by `data/`, so a
schema change breaks the fixture build rather than silently diverging from it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SEED_FILE = Path(__file__).resolve().parent / "seed.json"

PATIENT_TABLES = (
    "patients",
    "encounters",
    "observations",
    "medications",
    "conditions",
    "procedures",
    "allergies",
    "clinical_notes",
)
ROW_LIMITS = {"observations": 60, "procedures": 10, "conditions": 10, "encounters": 8}


def _rows(
    connection: sqlite3.Connection, query: str, parameters: tuple[object, ...]
) -> list[list[object]]:
    cursor = connection.execute(query, parameters)
    return [list(row) for row in cursor.fetchall()]


SUMMARY_PLACEHOLDER = (
    "[Summary omitted from the committed fixture. MedlinePlus permits linking to and "
    "displaying returned data but not copying its pages, so only the citable metadata "
    "is committed; the summary is fetched at build time. See NOTICE.md.]"
)

# education_pages: code_system, code, title, url, summary_html, attribution, retrieved_at
SUMMARY_COLUMN = 4


def _without_summary(page: list[object]) -> list[object]:
    """Drop the page body before it reaches git.

    The build cache may hold the summary NLM returned — that is the caching NLM
    recommends. A committed fixture is a different thing: it is published, it is
    permanent, and it would be a copy of MedlinePlus content sitting in a public
    repository. The tests only need the citable metadata, so that is all the
    seed carries.
    """
    trimmed = list(page)
    trimmed[SUMMARY_COLUMN] = SUMMARY_PLACEHOLDER
    return trimmed


def build() -> dict[str, object]:
    records = sqlite3.connect(DATA_DIR / "records.db")
    education = sqlite3.connect(DATA_DIR / "education.db")
    policy = sqlite3.connect(DATA_DIR / "policy.db")
    try:
        bindings = json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))
        case_four = next(
            case for case in bindings["canonical_cases"] if case["case_id"] == "c04-critical-value"
        )
        primary = case_four["binding"]["patient_with_critical_potassium"]
        injection = next(
            case
            for case in bindings["canonical_cases"]
            if case["case_id"] == "c07-indirect-injection"
        )["binding"]["patient_with_injection_note"]
        patients = [primary, injection]

        seed: dict[str, object] = {"patient_ids": patients}
        by_table: dict[str, list[list[object]]] = {}
        for table in PATIENT_TABLES:
            limit = ROW_LIMITS.get(table, 25)
            collected: list[list[object]] = []
            for patient_id in patients:
                collected.extend(
                    _rows(
                        records,
                        f"SELECT * FROM {table} WHERE patient_id = ? LIMIT ?",  # noqa: S608
                        (patient_id, limit),
                    )
                )
            by_table[table] = collected
            seed[table] = collected

        seed["reference_ranges"] = _rows(records, "SELECT * FROM reference_ranges", ())
        seed["scenario_fixtures"] = _rows(records, "SELECT * FROM scenario_fixtures", ())

        codes = {str(row[5]) for row in by_table["observations"]}
        rxcuis = {str(row[5]) for row in by_table["medications"]}
        pages: list[list[object]] = []
        gaps: list[list[object]] = []
        for code in sorted(codes):
            pages.extend(
                _rows(
                    education,
                    "SELECT * FROM education_pages WHERE code_system = 'loinc' AND code = ?",
                    (code,),
                )
            )
            gaps.extend(
                _rows(
                    education,
                    "SELECT * FROM coverage_gaps WHERE code_system = 'loinc' AND code = ?",
                    (code,),
                )
            )
        for rxcui in sorted(rxcuis):
            pages.extend(
                _rows(
                    education,
                    "SELECT * FROM education_pages WHERE code_system = 'rxcui' AND code = ?",
                    (rxcui,),
                )
            )
            gaps.extend(
                _rows(
                    education,
                    "SELECT * FROM coverage_gaps WHERE code_system = 'rxcui' AND code = ?",
                    (rxcui,),
                )
            )
        seed["education_pages"] = [_without_summary(page) for page in pages]
        seed["coverage_gaps"] = gaps
        seed["policy_rules"] = _rows(policy, "SELECT * FROM policy_rules", ())

        # Coverage is a property of the education pipeline over the whole
        # population, not of the two patients in this fixture. Committing the
        # numbers — never the content — lets the docs chart state a real
        # coverage figure and still regenerate deterministically in CI.
        coverage_file = DATA_DIR / "education_coverage.json"
        if coverage_file.exists():
            seed["coverage_summary"] = json.loads(coverage_file.read_text(encoding="utf-8"))
        return seed
    finally:
        records.close()
        education.close()
        policy.close()


def main() -> int:
    seed = build()
    SEED_FILE.write_text(json.dumps(seed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {key: len(value) for key, value in seed.items() if isinstance(value, list)}
    print(f"wrote {SEED_FILE.name}")
    for table, count in sorted(counts.items()):
        print(f"  {table:<20} {count:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
