"""Retrieval: exact lookup first, vectors only where needed (docs/PLAN.md §5.6).

`exact` is the LOINC/RxCUI code join and the reference-band lookup. `note_search`
is the Qdrant-backed per-patient note search, where the collection filter is a
security control, not an optimisation.
"""

from navigator.retrieval.exact import lab_education, medication_education, reference_band
from navigator.retrieval.note_search import NoteHit, NoteSearch

__all__ = ["NoteHit", "NoteSearch", "lab_education", "medication_education", "reference_band"]
