"""Retrieve a patient's recorded allergies.

Patient-scoped by the executor. Allergies inform safety-aware answers, so this
tool exists even though the sample cohort may record none for a given patient --
an empty list is a valid, meaningful answer (docs/PLAN.md §3.4).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import AllergiesResult, AllergyItem, PatientListArgs
from navigator.store import RecordStore

NAME = "get_allergies"


def build_get_allergies_tool(record_store: RecordStore) -> StructuredTool:
    def get_allergies(patient_id: str, limit: int | None = None) -> AllergiesResult:
        """Retrieve the patient's recorded allergies -- substance, reaction and
        severity -- for safety-aware responses.

        Args:
            patient_id: The patient whose allergies to read.
            limit: Maximum allergies to return; capped to the scope's row cap.

        Returns:
            The allergies, most recent first; an empty list is a valid answer.
        """
        rows = record_store.allergies(patient_id, limit=limit)
        return AllergiesResult(
            patient_id=patient_id,
            allergies=[
                AllergyItem(
                    allergy_id=r.allergy_id,
                    recorded_on=r.recorded_on,
                    code=r.code,
                    description=r.description,
                    allergy_type=r.allergy_type,
                    category=r.category,
                    severity=r.severity,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(func=get_allergies, name=NAME, args_schema=PatientListArgs)
