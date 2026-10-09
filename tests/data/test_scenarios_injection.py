"""The planted critical potassium has to be what "my most recent potassium" returns.

Synthea records its own, normal potassium on the patient's latest encounter date; a planted
value on that same date lost the tie-break (observation_id order) and never reached post-flight.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from data.build_store import SCHEMA
from data.scenarios import FIXTURE_SCHEMA, inject_critical_potassium
from navigator.store import RecordStore

PATIENT = "p-1"
ENCOUNTER_DAY = "2026-06-30"


def _store_with_same_day_normal_potassium(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA)
    connection.executescript(FIXTURE_SCHEMA)
    connection.execute(
        "INSERT INTO patients VALUES (?, 'Test', 'Patient', '1980-01-01', 'F', 'en', 'basic')",
        (PATIENT,),
    )
    connection.execute(
        "INSERT INTO encounters VALUES ('e-1', ?, ?, NULL, 'wellness', 'x', 'Visit', NULL, NULL)",
        (PATIENT, ENCOUNTER_DAY),
    )
    # Sorts before "obs-fixture-..." so it wins a same-date tie, as in the real build.
    connection.execute(
        "INSERT INTO observations VALUES ('obs-d5ac', ?, 'e-1', ?, 'laboratory', '6298-4', "
        "'Potassium [Moles/volume] in Blood', 4.9, NULL, 'mmol/L', 'numeric')",
        (PATIENT, ENCOUNTER_DAY),
    )
    connection.commit()
    return connection


def test_planted_critical_potassium_is_the_most_recent_potassium(tmp_path: Path) -> None:
    db_path = tmp_path / "records.db"
    connection = _store_with_same_day_normal_potassium(db_path)
    inject_critical_potassium(connection, PATIENT)
    connection.commit()
    connection.close()

    (latest,) = RecordStore(db_path).observations(PATIENT, analyte="potassium", limit=1)

    assert latest.value_number == 6.9
