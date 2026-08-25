"""Retrieve a patient's recorded conditions (problem list).

Patient-scoped and row-capped by the executor (docs/PLAN.md §3.4, §5.5).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import ConditionItem, ConditionsResult, PatientListArgs
from navigator.store import RecordStore

NAME = "get_conditions"


def build_get_conditions_tool(record_store: RecordStore) -> StructuredTool:
    def get_conditions(patient_id: str, limit: int | None = None) -> ConditionsResult:
        """Retrieve the patient's recorded conditions with onset and resolution
        dates, for context on why a test or medication was ordered.

        Args:
            patient_id: The patient whose conditions to read.
            limit: Maximum conditions to return; capped to the scope's row cap.

        Returns:
            The conditions, most recent onset first; an empty list is valid.
        """
        rows = record_store.conditions(patient_id, limit=limit)
        return ConditionsResult(
            patient_id=patient_id,
            conditions=[
                ConditionItem(
                    condition_id=r.condition_id,
                    encounter_id=r.encounter_id,
                    onset_on=r.onset_on,
                    resolved_on=r.resolved_on,
                    code=r.code,
                    description=r.description,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(func=get_conditions, name=NAME, args_schema=PatientListArgs)
