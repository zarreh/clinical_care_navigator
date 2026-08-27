"""Canonical-eval fixture stores.

Built from the same committed seed the unit tests use
(`tests/fixtures/seed.json`), enriched with the one fact that narrower seed
does not carry: an A1c observation, needed by `data.scenarios.bind()` to
resolve cases 1, 4, 15 and 16 to a concrete patient. Everything else
`bind()` needs — a second patient, an already-planted injection-fixture
note (case 7), and an analyte no patient has recorded (case 14) — is
already present in the seed.

Deliberately independent of `tests/fixtures` (evals is not test code): this
module reads the same seed file but does not import test helpers.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data.build_store import SCHEMA as RECORDS_SCHEMA
from data.fetch_education import SCHEMA as EDUCATION_SCHEMA
from data.generate_policy_rules import SCHEMA as POLICY_SCHEMA
from data.scenarios import A1C_LOINC, FIXTURE_SCHEMA

SEED_FILE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "seed.json"

RECORD_TABLES = (
    "patients",
    "encounters",
    "observations",
    "medications",
    "conditions",
    "procedures",
    "allergies",
    "clinical_notes",
    "reference_ranges",
    "scenario_fixtures",
)
EDUCATION_TABLES = ("education_pages", "coverage_gaps")


@dataclass(frozen=True)
class EvalStores:
    records_db: Path
    education_db: Path
    policy_db: Path


def _insert(connection: sqlite3.Connection, table: str, rows: list[list[Any]]) -> None:
    if not rows:
        return
    placeholders = ", ".join("?" for _ in rows[0])
    connection.executemany(
        f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})",  # noqa: S608 - fixed table names
        [tuple(row) for row in rows],
    )


def _add_a1c_observation(seed: dict[str, Any], patient_id: str) -> None:
    """Case 1 needs a lab-education question over a real result; cases 4, 15
    and 16 need the same patient for the critical-value override, the
    reading-level target, and the language-detection case (§4.5). Giving one
    patient (the seed's basic-literacy one) an A1c satisfies `with_a1c` and
    `basic_with_a1c` together."""
    encounter = next(e for e in seed["encounters"] if e[1] == patient_id)
    encounter_id, started_at = encounter[0], encounter[2]
    seed["observations"].append(
        [
            f"obs-eval-a1c-{patient_id[:8]}",
            patient_id,
            encounter_id,
            started_at,
            "laboratory",
            A1C_LOINC,
            "Hemoglobin A1c/Hemoglobin.total in Blood",
            7.8,
            None,
            "%",
            "numeric",
        ]
    )


def build_eval_stores(destination: Path) -> EvalStores:
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    _add_a1c_observation(seed, seed["patient_ids"][0])
    destination.mkdir(parents=True, exist_ok=True)

    records_db = destination / "records.db"
    education_db = destination / "education.db"
    policy_db = destination / "policy.db"

    records = sqlite3.connect(records_db)
    try:
        records.executescript(RECORDS_SCHEMA)
        records.executescript(FIXTURE_SCHEMA)
        for table in RECORD_TABLES:
            _insert(records, table, seed.get(table, []))
        records.commit()
    finally:
        records.close()

    education = sqlite3.connect(education_db)
    try:
        education.executescript(EDUCATION_SCHEMA)
        for table in EDUCATION_TABLES:
            _insert(education, table, seed.get(table, []))
        education.commit()
    finally:
        education.close()

    policy = sqlite3.connect(policy_db)
    try:
        policy.executescript(POLICY_SCHEMA)
        _insert(policy, "policy_rules", seed.get("policy_rules", []))
        policy.commit()
    finally:
        policy.close()

    return EvalStores(records_db=records_db, education_db=education_db, policy_db=policy_db)
