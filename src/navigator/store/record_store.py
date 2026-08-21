"""Read-only repository over the synthetic patient record.

Two properties matter more here than in an ordinary repository, and both are
enforced in this file rather than trusted to callers:

**Every query is patient-scoped.** There is no method that reads a clinical row
without a `patient_id` argument, and every statement is parameterised. A tool
cannot ask this store for "all labs" because the question cannot be expressed
(docs/PLAN.md §3.3).

**Every read is capped.** `row_cap` is both a cost control and a
minimum-necessary control under 45 CFR 164.502(b), which is why the cap lives in
the store rather than in the caller that might forget it (§5.5).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from navigator.store.models import (
    Allergy,
    ClinicalNote,
    Condition,
    Encounter,
    LiteracyLevel,
    Medication,
    Observation,
    Patient,
    Procedure,
    ReferenceRange,
)

DEFAULT_ROW_CAP = 25

_PATIENT_COLUMNS = (
    "patient_id, given_name, family_name, birth_date, gender, language, health_literacy_level"
)
_OBSERVATION_COLUMNS = (
    "observation_id, patient_id, encounter_id, taken_at, category, loinc_code, "
    "description, value_number, value_text, units, value_type"
)
_MEDICATION_COLUMNS = (
    "medication_id, patient_id, encounter_id, started_on, stopped_on, rxcui, "
    "description, reason_description"
)
_ENCOUNTER_COLUMNS = (
    "encounter_id, patient_id, started_at, stopped_at, encounter_class, code, "
    "description, reason_code, reason_description"
)
_CONDITION_COLUMNS = (
    "condition_id, patient_id, encounter_id, onset_on, resolved_on, code, description"
)
_PROCEDURE_COLUMNS = (
    "procedure_id, patient_id, encounter_id, performed_on, code, description, reason_description"
)
_ALLERGY_COLUMNS = (
    "allergy_id, patient_id, recorded_on, code, description, allergy_type, category, severity"
)
_NOTE_COLUMNS = "note_id, patient_id, encounter_id, authored_at, note_type, body, fixture_kind"
_RANGE_COLUMNS = (
    "loinc_code, analyte, specimen, units, reference_low, reference_high, "
    "reference_source_name, reference_source_url, reference_source_quote, "
    "critical_low, critical_high, critical_source_name, critical_source_url, "
    "critical_source_quote, population, notes"
)


class RecordStore:
    """Patient-scoped, row-capped reads over `records.db`."""

    def __init__(self, db_path: Path, row_cap: int = DEFAULT_ROW_CAP) -> None:
        # check_same_thread=False: LangGraph runs sync tools in a worker thread
        # pool. This store is read-only, so cross-thread use is safe.
        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        self._row_cap = row_cap

    def close(self) -> None:
        self._connection.close()

    @property
    def row_cap(self) -> int:
        return self._row_cap

    def _cap(self, limit: int | None) -> int:
        """Clamp a caller's limit to the store's cap. A caller can ask for less."""
        if limit is None:
            return self._row_cap
        return max(1, min(limit, self._row_cap))

    def get_patient(self, patient_id: str) -> Patient | None:
        row = self._connection.execute(
            f"SELECT {_PATIENT_COLUMNS} FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if row is None:
            return None
        literacy: LiteracyLevel = row[6]
        return Patient(
            patient_id=row[0],
            given_name=row[1],
            family_name=row[2],
            birth_date=row[3],
            gender=row[4],
            language=row[5],
            health_literacy_level=literacy,
        )

    def observations(
        self,
        patient_id: str,
        *,
        loinc_code: str | None = None,
        category: str | None = "laboratory",
        limit: int | None = None,
    ) -> list[Observation]:
        clauses = ["patient_id = ?"]
        parameters: list[object] = [patient_id]
        if loinc_code:
            clauses.append("loinc_code = ?")
            parameters.append(loinc_code)
        if category:
            clauses.append("category = ?")
            parameters.append(category)
        parameters.append(self._cap(limit))
        rows = self._connection.execute(
            f"SELECT {_OBSERVATION_COLUMNS} FROM observations WHERE {' AND '.join(clauses)} "
            "ORDER BY taken_at DESC, observation_id ASC LIMIT ?",
            parameters,
        ).fetchall()
        return [Observation(*row) for row in rows]

    def medications(self, patient_id: str, *, limit: int | None = None) -> list[Medication]:
        rows = self._connection.execute(
            f"SELECT {_MEDICATION_COLUMNS} FROM medications WHERE patient_id = ? "
            "ORDER BY started_on DESC, medication_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [Medication(*row) for row in rows]

    def encounters(self, patient_id: str, *, limit: int | None = None) -> list[Encounter]:
        rows = self._connection.execute(
            f"SELECT {_ENCOUNTER_COLUMNS} FROM encounters WHERE patient_id = ? "
            "ORDER BY started_at DESC, encounter_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [Encounter(*row) for row in rows]

    def conditions(self, patient_id: str, *, limit: int | None = None) -> list[Condition]:
        rows = self._connection.execute(
            f"SELECT {_CONDITION_COLUMNS} FROM conditions WHERE patient_id = ? "
            "ORDER BY onset_on DESC, condition_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [Condition(*row) for row in rows]

    def procedures(self, patient_id: str, *, limit: int | None = None) -> list[Procedure]:
        rows = self._connection.execute(
            f"SELECT {_PROCEDURE_COLUMNS} FROM procedures WHERE patient_id = ? "
            "ORDER BY performed_on DESC, procedure_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [Procedure(*row) for row in rows]

    def allergies(self, patient_id: str, *, limit: int | None = None) -> list[Allergy]:
        rows = self._connection.execute(
            f"SELECT {_ALLERGY_COLUMNS} FROM allergies WHERE patient_id = ? "
            "ORDER BY recorded_on DESC, allergy_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [Allergy(*row) for row in rows]

    def notes(self, patient_id: str, *, limit: int | None = None) -> list[ClinicalNote]:
        rows = self._connection.execute(
            f"SELECT {_NOTE_COLUMNS} FROM clinical_notes WHERE patient_id = ? "
            "ORDER BY authored_at DESC, note_id ASC LIMIT ?",
            (patient_id, self._cap(limit)),
        ).fetchall()
        return [ClinicalNote(*row) for row in rows]

    def reference_range(self, loinc_code: str) -> ReferenceRange | None:
        """The curated band for one analyte, or None if the table does not cover it.

        None is a first-class answer: the assistant quotes a range or says it
        does not have one. It never estimates a band (§3.7).
        """
        row = self._connection.execute(
            f"SELECT {_RANGE_COLUMNS} FROM reference_ranges WHERE loinc_code = ? "
            "ORDER BY specimen ASC LIMIT 1",
            (loinc_code,),
        ).fetchone()
        return ReferenceRange(*row) if row else None

    def reference_ranges(self) -> list[ReferenceRange]:
        rows = self._connection.execute(
            f"SELECT {_RANGE_COLUMNS} FROM reference_ranges ORDER BY loinc_code ASC, specimen ASC"
        ).fetchall()
        return [ReferenceRange(*row) for row in rows]

    def patient_ids(self) -> list[str]:
        """Every patient id. Used by the data profile and the eval harness only."""
        return [str(row[0]) for row in self._connection.execute("SELECT patient_id FROM patients")]
