"""Retrieve a patient's clinical notes, rendered from the structured record.

Synthea has no free-text notes, so these are composed deterministically from the
record (docs/PLAN.md §4.3) -- the docs say so plainly rather than implying they
were authored. Patient-scoped and row-capped by the executor.

This is *structured*-note retrieval by SQL. Open-ended free-text note *search*
is a separate, Qdrant-backed, per-patient-filtered capability that arrives in
Phase 4 (§5.6); this tool never leaves the one patient's own notes.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import ClinicalNoteItem, ClinicalNotesResult, PatientListArgs
from navigator.store import RecordStore

NAME = "get_clinical_notes"


def build_get_clinical_notes_tool(record_store: RecordStore) -> StructuredTool:
    def get_clinical_notes(patient_id: str, limit: int | None = None) -> ClinicalNotesResult:
        """Retrieve the patient's most recent clinical notes for "what happened
        at my last visit?" style summaries.

        Args:
            patient_id: The patient whose notes to read.
            limit: Maximum notes to return; capped to the scope's row cap.

        Returns:
            The notes, most recent first; an empty list is a valid answer.
        """
        rows = record_store.notes(patient_id, limit=limit)
        return ClinicalNotesResult(
            patient_id=patient_id,
            notes=[
                ClinicalNoteItem(
                    note_id=r.note_id,
                    encounter_id=r.encounter_id,
                    authored_at=r.authored_at,
                    note_type=r.note_type,
                    body=r.body,
                    fixture_kind=r.fixture_kind,
                )
                for r in rows
            ],
            count=len(rows),
        )

    return StructuredTool.from_function(
        func=get_clinical_notes, name=NAME, args_schema=PatientListArgs
    )
