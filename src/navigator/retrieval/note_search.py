"""Per-patient note search over Qdrant (docs/PLAN.md §5.6).

Free-text note search is the one place a vector store is the right tool — but
the per-patient collection filter is a **security control**, not an optimisation.
A note vector search that could return another patient's note is the same class
of defect as an unscoped SQL query, and it gets the same test: the filter is
applied at the Qdrant collection-filter level, so a match outside the patient's
own notes is not merely discouraged, it is not returned.

Every note vector carries its `patient_id` as payload, and every query filters
on it. The test asserts a query for one patient never returns a note whose
payload `patient_id` differs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

NOTES_COLLECTION = "clinical_notes"
_TOPICS_COLLECTION = "health_topics"


@dataclass(frozen=True)
class NoteHit:
    note_id: str
    patient_id: str
    body: str
    score: float


class NoteSearch:
    """Qdrant-backed note search, always filtered to one patient."""

    def __init__(self, client: QdrantClient, embed) -> None:  # type: ignore[no-untyped-def]
        self._client = client
        self._embed = embed

    def ensure_collection(self, vector_size: int) -> None:
        if not self._client.collection_exists(NOTES_COLLECTION):
            self._client.create_collection(
                collection_name=NOTES_COLLECTION,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def index_note(self, note_id: str, patient_id: str, body: str) -> None:
        vector = self._embed(body)
        # Qdrant point ids must be UUIDs or ints; derive a stable UUID from the
        # note id and keep the original in the payload.
        point_id = uuid.uuid5(uuid.NAMESPACE_URL, f"note:{note_id}")
        self._client.upsert(
            collection_name=NOTES_COLLECTION,
            points=[
                PointStruct(
                    id=str(point_id),
                    vector=vector,
                    payload={"patient_id": patient_id, "body": body, "note_id": note_id},
                )
            ],
        )

    def search(self, patient_id: str, query: str, *, limit: int = 5) -> list[NoteHit]:
        """Search only this patient's own notes.

        The patient filter is mandatory and applied at the collection-filter
        level — there is no code path that searches notes without it.
        """
        vector = self._embed(query)
        patient_filter = Filter(
            must=[FieldCondition(key="patient_id", match=MatchValue(value=patient_id))]
        )
        results = self._client.query_points(
            collection_name=NOTES_COLLECTION,
            query=vector,
            query_filter=patient_filter,
            limit=limit,
            with_payload=True,
        ).points
        hits: list[NoteHit] = []
        for point in results:
            payload = point.payload or {}
            hits.append(
                NoteHit(
                    note_id=str(payload["note_id"]),
                    patient_id=str(payload["patient_id"]),
                    body=str(payload["body"]),
                    score=float(point.score),
                )
            )
        return hits
