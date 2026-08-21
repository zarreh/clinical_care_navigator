"""Build the typed SQLite portal schema from the Synthea CSV export.

The source notebook read four CSVs into module-global pandas frames and let
every tool reach into them. This script produces a **typed store** instead, with
one table per record class, explicit column types and indexes on the two columns
every scoped query filters by (docs/PLAN.md §3.6).

Two fields have no Synthea equivalent and are **assigned** here rather than
discovered: `language` and `health_literacy_level`. They are assigned
deterministically from the patient id, so a rebuild produces the same population,
and the docs say plainly that they are assigned rather than authored — the same
honesty rule that governs rendered notes (§4.3).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
SYNTHEA_DIR = DATA_DIR / "synthea"
RANGES_CSV = DATA_DIR / "lab_reference_ranges.csv"
DEFAULT_DB = DATA_DIR / "records.db"

LANGUAGES = ("en", "en", "en", "en", "es")
LITERACY_LEVELS = ("basic", "intermediate", "proficient")

SCHEMA = """
CREATE TABLE patients (
    patient_id             TEXT PRIMARY KEY,
    given_name             TEXT NOT NULL,
    family_name            TEXT NOT NULL,
    birth_date             TEXT NOT NULL,
    gender                 TEXT NOT NULL,
    language               TEXT NOT NULL,
    health_literacy_level  TEXT NOT NULL
);

CREATE TABLE encounters (
    encounter_id       TEXT PRIMARY KEY,
    patient_id         TEXT NOT NULL REFERENCES patients(patient_id),
    started_at         TEXT NOT NULL,
    stopped_at         TEXT,
    encounter_class    TEXT NOT NULL,
    code               TEXT NOT NULL,
    description        TEXT NOT NULL,
    reason_code        TEXT,
    reason_description TEXT
);

CREATE TABLE observations (
    observation_id TEXT PRIMARY KEY,
    patient_id     TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id   TEXT NOT NULL,
    taken_at       TEXT NOT NULL,
    category       TEXT NOT NULL,
    loinc_code     TEXT NOT NULL,
    description    TEXT NOT NULL,
    value_number   REAL,
    value_text     TEXT,
    units          TEXT,
    value_type     TEXT NOT NULL
);

CREATE TABLE medications (
    medication_id      TEXT PRIMARY KEY,
    patient_id         TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id       TEXT NOT NULL,
    started_on         TEXT NOT NULL,
    stopped_on         TEXT,
    rxcui              TEXT NOT NULL,
    description        TEXT NOT NULL,
    reason_description TEXT
);

CREATE TABLE conditions (
    condition_id TEXT PRIMARY KEY,
    patient_id   TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id TEXT NOT NULL,
    onset_on     TEXT NOT NULL,
    resolved_on  TEXT,
    code         TEXT NOT NULL,
    description  TEXT NOT NULL
);

CREATE TABLE procedures (
    procedure_id       TEXT PRIMARY KEY,
    patient_id         TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id       TEXT NOT NULL,
    performed_on       TEXT NOT NULL,
    code               TEXT NOT NULL,
    description        TEXT NOT NULL,
    reason_description TEXT
);

CREATE TABLE allergies (
    allergy_id   TEXT PRIMARY KEY,
    patient_id   TEXT NOT NULL REFERENCES patients(patient_id),
    recorded_on  TEXT NOT NULL,
    code         TEXT NOT NULL,
    description  TEXT NOT NULL,
    allergy_type TEXT,
    category     TEXT,
    severity     TEXT
);

-- Rendered by data/render_notes.py, never authored. Created here so the schema
-- lives in one place.
CREATE TABLE clinical_notes (
    note_id      TEXT PRIMARY KEY,
    patient_id   TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id TEXT NOT NULL,
    authored_at  TEXT NOT NULL,
    note_type    TEXT NOT NULL,
    body         TEXT NOT NULL,
    fixture_kind TEXT
);

CREATE TABLE reference_ranges (
    loinc_code             TEXT NOT NULL,
    analyte                TEXT NOT NULL,
    specimen               TEXT NOT NULL,
    units                  TEXT NOT NULL,
    reference_low          REAL,
    reference_high         REAL,
    reference_source_name  TEXT NOT NULL,
    reference_source_url   TEXT NOT NULL,
    reference_source_quote TEXT NOT NULL,
    critical_low           REAL,
    critical_high          REAL,
    critical_source_name   TEXT,
    critical_source_url    TEXT,
    critical_source_quote  TEXT,
    population             TEXT NOT NULL,
    notes                  TEXT,
    PRIMARY KEY (loinc_code, specimen)
);

CREATE INDEX idx_observations_patient ON observations(patient_id, loinc_code);
CREATE INDEX idx_medications_patient ON medications(patient_id);
CREATE INDEX idx_conditions_patient ON conditions(patient_id);
CREATE INDEX idx_procedures_patient ON procedures(patient_id);
CREATE INDEX idx_encounters_patient ON encounters(patient_id, started_at);
CREATE INDEX idx_notes_patient ON clinical_notes(patient_id, authored_at);
"""


def stable_id(prefix: str, *parts: str) -> str:
    """A reproducible surrogate key.

    Synthea gives observations, medications and conditions no identifier of
    their own, but every row this app cites has to be addressable — an answer
    that says "your record shows X" must be able to name the row it read
    (§6.1). Hashing the natural key gives that without a build-order dependency.
    """
    digest = hashlib.blake2b("|".join(parts).encode("utf-8"), digest_size=8).hexdigest()
    return f"{prefix}-{digest}"


def assign_from_id(patient_id: str, options: tuple[str, ...]) -> str:
    """Deterministically pick one option for a patient. Assigned, not discovered."""
    digest = hashlib.blake2b(patient_id.encode("utf-8"), digest_size=4).digest()
    return options[int.from_bytes(digest, "big") % len(options)]


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def as_date(value: str) -> str:
    """Synthea mixes `YYYY-MM-DD` and `YYYY-MM-DDTHH:MM:SSZ`. Keep the date."""
    return value.split("T", 1)[0] if value else ""


def optional(value: str) -> str | None:
    return value or None


def as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_cohort() -> list[str]:
    cohort_file = SYNTHEA_DIR / "cohort.txt"
    if not cohort_file.exists():
        raise SystemExit("No cohort found. Run `python -m data.fetch_synthea` first.")
    lines = cohort_file.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def insert_patients(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows = [
        (
            row["Id"],
            row["FIRST"],
            row["LAST"],
            row["BIRTHDATE"],
            row["GENDER"],
            assign_from_id(row["Id"] + ":lang", LANGUAGES),
            assign_from_id(row["Id"] + ":literacy", LITERACY_LEVELS),
        )
        for row in read_csv(SYNTHEA_DIR / "patients.csv")
        if row["Id"] in cohort
    ]
    connection.executemany("INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_encounters(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows = [
        (
            row["Id"],
            row["PATIENT"],
            as_date(row["START"]),
            optional(as_date(row["STOP"])),
            row["ENCOUNTERCLASS"],
            row["CODE"],
            row["DESCRIPTION"],
            optional(row["REASONCODE"]),
            optional(row["REASONDESCRIPTION"]),
        )
        for row in read_csv(SYNTHEA_DIR / "encounters.csv")
        if row["PATIENT"] in cohort
    ]
    connection.executemany("INSERT INTO encounters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_observations(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for row in read_csv(SYNTHEA_DIR / "observations.csv"):
        if row["PATIENT"] not in cohort:
            continue
        taken_at = as_date(row["DATE"])
        observation_id = stable_id("obs", row["PATIENT"], row["ENCOUNTER"], taken_at, row["CODE"])
        if observation_id in seen:
            continue
        seen.add(observation_id)
        numeric = as_float(row["VALUE"]) if row["TYPE"] == "numeric" else None
        rows.append(
            (
                observation_id,
                row["PATIENT"],
                row["ENCOUNTER"],
                taken_at,
                row["CATEGORY"],
                row["CODE"],
                row["DESCRIPTION"],
                numeric,
                None if numeric is not None else row["VALUE"],
                optional(row["UNITS"]),
                row["TYPE"],
            )
        )
    connection.executemany(
        "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    return len(rows)


def insert_medications(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for row in read_csv(SYNTHEA_DIR / "medications.csv"):
        if row["PATIENT"] not in cohort:
            continue
        started = as_date(row["START"])
        medication_id = stable_id("med", row["PATIENT"], row["ENCOUNTER"], started, row["CODE"])
        if medication_id in seen:
            continue
        seen.add(medication_id)
        rows.append(
            (
                medication_id,
                row["PATIENT"],
                row["ENCOUNTER"],
                started,
                optional(as_date(row["STOP"])),
                row["CODE"],
                row["DESCRIPTION"],
                optional(row["REASONDESCRIPTION"]),
            )
        )
    connection.executemany("INSERT INTO medications VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_conditions(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for row in read_csv(SYNTHEA_DIR / "conditions.csv"):
        if row["PATIENT"] not in cohort:
            continue
        onset = as_date(row["START"])
        condition_id = stable_id("cond", row["PATIENT"], row["ENCOUNTER"], onset, row["CODE"])
        if condition_id in seen:
            continue
        seen.add(condition_id)
        rows.append(
            (
                condition_id,
                row["PATIENT"],
                row["ENCOUNTER"],
                onset,
                optional(as_date(row["STOP"])),
                row["CODE"],
                row["DESCRIPTION"],
            )
        )
    connection.executemany("INSERT INTO conditions VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_procedures(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for row in read_csv(SYNTHEA_DIR / "procedures.csv"):
        if row["PATIENT"] not in cohort:
            continue
        performed = as_date(row["START"])
        procedure_id = stable_id("proc", row["PATIENT"], row["ENCOUNTER"], performed, row["CODE"])
        if procedure_id in seen:
            continue
        seen.add(procedure_id)
        rows.append(
            (
                procedure_id,
                row["PATIENT"],
                row["ENCOUNTER"],
                performed,
                row["CODE"],
                row["DESCRIPTION"],
                optional(row["REASONDESCRIPTION"]),
            )
        )
    connection.executemany("INSERT INTO procedures VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_allergies(connection: sqlite3.Connection, cohort: set[str]) -> int:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for row in read_csv(SYNTHEA_DIR / "allergies.csv"):
        if row["PATIENT"] not in cohort:
            continue
        recorded = as_date(row["START"])
        allergy_id = stable_id("alg", row["PATIENT"], recorded, row["CODE"])
        if allergy_id in seen:
            continue
        seen.add(allergy_id)
        rows.append(
            (
                allergy_id,
                row["PATIENT"],
                recorded,
                row["CODE"],
                row["DESCRIPTION"],
                optional(row["TYPE"]),
                optional(row["CATEGORY"]),
                optional(row["SEVERITY1"]),
            )
        )
    connection.executemany("INSERT INTO allergies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def insert_reference_ranges(connection: sqlite3.Connection, ranges_csv: Path = RANGES_CSV) -> int:
    """Load the curated range table, failing loudly on an uncited row.

    Launch gate §11.8: every reference-range row cites its source, and the build
    fails if not. A range with no published source behind it is exactly the kind
    of number this app must never quote.
    """
    rows: list[tuple[Any, ...]] = []
    for line, row in enumerate(read_csv(ranges_csv), start=2):
        loinc = row["loinc_code"]
        if not row["reference_source_url"] or not row["reference_source_quote"]:
            raise SystemExit(
                f"{ranges_csv.name} line {line}: reference band for {loinc} has no cited source. "
                "Every band must quote a published source (docs/PLAN.md §4.3)."
            )
        has_critical = bool(row["critical_low"] or row["critical_high"])
        if has_critical and not (row["critical_source_url"] and row["critical_source_quote"]):
            raise SystemExit(
                f"{ranges_csv.name} line {line}: critical band for {loinc} has no cited source. "
                "Leave the band empty rather than assert an uncited threshold."
            )
        rows.append(
            (
                loinc,
                row["analyte"],
                row["specimen"],
                row["units"],
                as_float(row["reference_low"]),
                as_float(row["reference_high"]),
                row["reference_source_name"],
                row["reference_source_url"],
                row["reference_source_quote"],
                as_float(row["critical_low"]),
                as_float(row["critical_high"]),
                optional(row["critical_source_name"]),
                optional(row["critical_source_url"]),
                optional(row["critical_source_quote"]),
                row["population"],
                optional(row["notes"]),
            )
        )
    connection.executemany(
        "INSERT INTO reference_ranges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    return len(rows)


def build(db_path: Path) -> None:
    cohort = load_cohort()
    scoped = set(cohort)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA)
        counts = {
            "patients": insert_patients(connection, scoped),
            "encounters": insert_encounters(connection, scoped),
            "observations": insert_observations(connection, scoped),
            "medications": insert_medications(connection, scoped),
            "conditions": insert_conditions(connection, scoped),
            "procedures": insert_procedures(connection, scoped),
            "allergies": insert_allergies(connection, scoped),
            "reference_ranges": insert_reference_ranges(connection),
        }
        connection.commit()
    finally:
        connection.close()

    for table, count in counts.items():
        print(f"  {table:<18} {count:>7,}")
    if counts["patients"] != len(cohort):
        raise SystemExit(f"Expected {len(cohort)} patients, wrote {counts['patients']}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    print("build_store")
    build(args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
