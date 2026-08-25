"""List a patient's most recent encounters for visit context.

Patient-scoped and row-capped by the executor (docs/PLAN.md §3.4, §5.5).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import EncounterItem, EncountersResult, PatientListArgs
from navigator.store import RecordStore

NAME = "list_patient_encounters"


def build_list_patient_encounters_tool(record_store: RecordStore) -> StructuredTool:
    def list_patient_encounters(patient_id: str, limit: int | None = None) -> EncountersResult:
        """List the patient's most recent encounters (visit type, reason,
        follow-up) for summarisation and navigation-style answers.

        Args:
            patient_id: The patient whose encounters to read.
            limit: Maximum encounters to return; capped to the scope's row cap.

        Returns:
            The encounters, most recent first; an empty list is a valid answer.
        """
        rows = record_store.encounters(patient_id, limit=limit)
        return EncountersResult(
            patient_id=patient_id,
            encounters=[
                EncounterItem(
                    encounter_id=r.encounter_id,
                    started_at=r.started_at,
                    stopped_at=r.stopped_at,
                    encounter_class=r.encounter_class,
                    code=r.code,
                    description=r.description,
                    reason_code=r.reason_code,
                    reason_description=r.reason_description,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(
        func=list_patient_encounters, name=NAME, args_schema=PatientListArgs
    )
