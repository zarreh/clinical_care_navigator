"""Retrieve a patient's recorded procedures.

Patient-scoped and row-capped by the executor (docs/PLAN.md §3.4, §5.5).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import PatientListArgs, ProcedureItem, ProceduresResult
from navigator.store import RecordStore

NAME = "get_procedures"


def build_get_procedures_tool(record_store: RecordStore) -> StructuredTool:
    def get_procedures(patient_id: str, limit: int | None = None) -> ProceduresResult:
        """Retrieve the patient's recorded procedures with the date performed,
        for context in a visit summary.

        Args:
            patient_id: The patient whose procedures to read.
            limit: Maximum procedures to return; capped to the scope's row cap.

        Returns:
            The procedures, most recent first; an empty list is a valid answer.
        """
        rows = record_store.procedures(patient_id, limit=limit)
        return ProceduresResult(
            patient_id=patient_id,
            procedures=[
                ProcedureItem(
                    procedure_id=r.procedure_id,
                    encounter_id=r.encounter_id,
                    performed_on=r.performed_on,
                    code=r.code,
                    description=r.description,
                    reason_description=r.reason_description,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(func=get_procedures, name=NAME, args_schema=PatientListArgs)
