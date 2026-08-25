"""Exact-first retrieval and the declared-gap path (§5.6, §4.2, case 14).

A LOINC/RxCUI with no vetted page returns an empty list — a declared gap, not a
substituted near-match and never generated text. The assistant says it has no
vetted education for the item and routes.
"""

from __future__ import annotations

from navigator.retrieval import lab_education, medication_education, reference_band
from navigator.store import EducationStore, RecordStore

UNCOVERED_LOINC = "99999-9"
UNCOVERED_RXCUI = "00000"


def test_uncovered_loinc_is_a_declared_gap(education_store: EducationStore) -> None:
    assert lab_education(education_store, UNCOVERED_LOINC) == []


def test_uncovered_rxcui_is_a_declared_gap(education_store: EducationStore) -> None:
    assert medication_education(education_store, UNCOVERED_RXCUI) == []


def test_covered_loinc_resolves(education_store: EducationStore) -> None:
    pages = lab_education(education_store, "18262-6")
    assert pages and all(page.url.startswith("https://") for page in pages)


def test_reference_band_missing_is_none_not_estimated(record_store: RecordStore) -> None:
    assert reference_band(record_store, UNCOVERED_LOINC) is None
