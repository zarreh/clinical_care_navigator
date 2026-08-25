"""Per-patient note search: the collection filter is a security control (§5.6).

A note vector search that could return another patient's note is the same class
of defect as an unscoped SQL query, and it gets the same test: a query for one
patient must never return a note whose payload patient_id differs. Runs against
an in-memory Qdrant with a deterministic embedding stub — no network, no model
download.
"""

from __future__ import annotations

import pytest

qdrant_client = pytest.importorskip("qdrant_client")
from qdrant_client import QdrantClient  # noqa: E402

from navigator.retrieval.note_search import NoteSearch  # noqa: E402


def _embed(text: str) -> list[float]:
    """A deterministic, offline embedding stub (8-dim, normalised)."""
    vector = [0.0] * 8
    for i, ch in enumerate(text):
        vector[i % 8] += (ord(ch) % 7) + 1
    norm = sum(x * x for x in vector) ** 0.5 or 1.0
    return [x / norm for x in vector]


@pytest.fixture
def note_search() -> NoteSearch:
    search = NoteSearch(QdrantClient(":memory:"), _embed)
    search.ensure_collection(vector_size=8)
    return search


def test_note_search_never_returns_another_patients_note(note_search: NoteSearch) -> None:
    note_search.index_note("n1", "P001", "patient one note about blood pressure")
    note_search.index_note("n2", "P002", "patient two note about blood pressure")
    note_search.index_note("n3", "P001", "patient one note about cholesterol")

    hits = note_search.search("P001", "blood pressure", limit=10)
    # The security property: no note whose payload patient_id differs.
    assert all(hit.patient_id == "P001" for hit in hits)
    assert "n2" not in {hit.note_id for hit in hits}


def test_note_search_returns_own_notes(note_search: NoteSearch) -> None:
    note_search.index_note("n1", "P001", "patient one note about blood pressure")
    hits = note_search.search("P001", "blood pressure", limit=5)
    assert any(hit.note_id == "n1" for hit in hits)


def test_note_search_empty_for_patient_with_no_notes(note_search: NoteSearch) -> None:
    note_search.index_note("n2", "P002", "patient two note")
    assert note_search.search("P999", "anything", limit=5) == []
