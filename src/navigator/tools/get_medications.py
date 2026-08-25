"""Retrieve a patient's medication list.

Patient-scoped and row-capped by the executor (docs/PLAN.md §3.4, §5.5).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import MedicationItem, MedicationsResult, PatientListArgs
from navigator.store import RecordStore

NAME = "get_medications"


def build_get_medications_tool(record_store: RecordStore) -> StructuredTool:
    def get_medications(patient_id: str, limit: int | None = None) -> MedicationsResult:
        """Retrieve the patient's recorded medications with their RxCUI codes,
        supporting medication-education answers.

        Args:
            patient_id: The patient whose medications to read.
            limit: Maximum medications to return; capped to the scope's row cap.

        Returns:
            The medications, most recently started first; an empty list is valid.
        """
        rows = record_store.medications(patient_id, limit=limit)
        return MedicationsResult(
            patient_id=patient_id,
            medications=[
                MedicationItem(
                    medication_id=r.medication_id,
                    encounter_id=r.encounter_id,
                    started_on=r.started_on,
                    stopped_on=r.stopped_on,
                    rxcui=r.rxcui,
                    description=r.description,
                    reason_description=r.reason_description,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(
        func=get_medications, name=NAME, args_schema=PatientListArgs
    )
