"""Exact-first retrieval (docs/PLAN.md §5.6, D-A3-5).

A LOINC code or an RxCUI is joined to the page MedlinePlus Connect returned for
exactly that code — a code join, not a similarity search. Semantically searching
for "Hemoglobin A1c" when the observation already carries LOINC `4548-4` would
substitute a probabilistic match for an exact one in the single place where
being wrong is expensive. Vectors are reserved for open-ended topics and note
search, where no exact key exists.
"""

from __future__ import annotations

from navigator.store import EducationStore, RecordStore
from navigator.store.models import EducationPage, ReferenceRange


def lab_education(education_store: EducationStore, loinc_code: str) -> list[EducationPage]:
    """Exact LOINC → education page join. Empty list is a declared gap (§4.2)."""
    return education_store.for_loinc(loinc_code)


def medication_education(education_store: EducationStore, rxcui: str) -> list[EducationPage]:
    """Exact RxCUI → education page join. Empty list is a declared gap (§4.2)."""
    return education_store.for_rxcui(rxcui)


def reference_band(record_store: RecordStore, loinc_code: str) -> ReferenceRange | None:
    """The curated band for one analyte, or None — never estimated (§3.7)."""
    return record_store.reference_range(loinc_code)
