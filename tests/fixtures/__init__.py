"""Offline fixture stores, built from a committed JSON seed.

Tests never touch the network and never need a rebuilt population. The schemas
come from `data/`, so a schema change breaks the fixture build loudly instead of
letting the tests drift away from the real store.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from data.build_store import SCHEMA as RECORDS_SCHEMA
from data.fetch_education import SCHEMA as EDUCATION_SCHEMA
from data.generate_policy_rules import SCHEMA as POLICY_SCHEMA
from data.scenarios import FIXTURE_SCHEMA

SEED_FILE = Path(__file__).resolve().parent / "seed.json"

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
class FixtureStores:
    records_db: Path
    education_db: Path
    policy_db: Path
    patient_ids: list[str]


def _insert(connection: sqlite3.Connection, table: str, rows: list[list[object]]) -> None:
    if not rows:
        return
    placeholders = ", ".join("?" for _ in rows[0])
    connection.executemany(
        f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})",  # noqa: S608 - fixed table names
        [tuple(row) for row in rows],
    )


def build_fixture_stores(destination: Path) -> FixtureStores:
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
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

    return FixtureStores(
        records_db=records_db,
        education_db=education_db,
        policy_db=policy_db,
        patient_ids=list(seed["patient_ids"]),
    )
