"""Retrieve a patient's recent laboratory results.

Exact LOINC filtering, never a similarity search: the observation already
carries the code, and being wrong here is expensive (docs/PLAN.md §5.6, D-A3-5).
Patient-scoped and row-capped by the executor.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import LabItem, LabsArgs, LabsResult
from navigator.store import RecordStore

NAME = "get_labs"


def build_get_labs_tool(record_store: RecordStore) -> StructuredTool:
    def get_labs(
        patient_id: str, loinc_code: str | None = None, limit: int | None = None
    ) -> LabsResult:
        """Retrieve recent laboratory results, optionally restricted to one
        analyte by exact LOINC code.

        Args:
            patient_id: The patient whose labs to read.
            loinc_code: Restrict to one analyte by exact LOINC code.
            limit: Maximum results to return; capped to the scope's row cap.

        Returns:
            The lab results, most recent first; an empty list is a valid answer.
        """
        rows = record_store.observations(patient_id, loinc_code=loinc_code, limit=limit)
        return LabsResult(
            patient_id=patient_id,
            labs=[
                LabItem(
                    observation_id=r.observation_id,
                    encounter_id=r.encounter_id,
                    taken_at=r.taken_at,
                    loinc_code=r.loinc_code,
                    description=r.description,
                    value_number=r.value_number,
                    value_text=r.value_text,
                    units=r.units,
                    value_type=r.value_type,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(func=get_labs, name=NAME, args_schema=LabsArgs)
