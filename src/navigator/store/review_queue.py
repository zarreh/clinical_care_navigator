"""Read-write repository over the clinician review queue (docs/PLAN.md §5.10).

`recommend`-band and post-flight-held drafts are not published; they are held
for a clinician, who approves, edits or declines them. Each row records the
LangGraph checkpoint `thread_id` the run suspended on, so a decision resumes the
**same** interrupted run from its checkpoint rather than starting a new one.

Like RunStore, this store creates its own schema on first use — it holds
operational state, not build-time data.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from navigator.store.models import ReviewItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    override_action TEXT,
    body TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_TERMINAL_BY_ACTION = {"approve": "approved", "edit": "edited", "decline": "declined"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _item_from_row(row: tuple[object, ...]) -> ReviewItem:
    return ReviewItem(
        id=str(row[0]),
        run_id=str(row[1]),
        thread_id=str(row[2]),
        patient_id=str(row[3]),
        reason=str(row[4]),
        override_action=None if row[5] is None else str(row[5]),
        body=str(row[6]),
        payload_json=str(row[7]),
        status=str(row[8]),
        created_at=str(row[9]),
        updated_at=str(row[10]),
    )


class ReviewQueue:
    """Persists drafts held for clinician review and their resolution. `GET
    /reviews` reads `list_pending`; `POST /reviews/{id}/decision` reads `get` and
    then `resolve`."""

    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def enqueue(
        self,
        review_id: str,
        run_id: str,
        thread_id: str,
        patient_id: str,
        reason: str,
        override_action: str | None,
        body: str,
        payload_json: str,
    ) -> None:
        now = _now()
        self._conn.execute(
            "INSERT INTO reviews (id, run_id, thread_id, patient_id, reason, "
            "override_action, body, payload_json, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (
                review_id,
                run_id,
                thread_id,
                patient_id,
                reason,
                override_action,
                body,
                payload_json,
                now,
                now,
            ),
        )
        self._conn.commit()

    def get(self, review_id: str) -> ReviewItem | None:
        row = self._conn.execute(
            "SELECT id, run_id, thread_id, patient_id, reason, override_action, body, "
            "payload_json, status, created_at, updated_at FROM reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
        return _item_from_row(row) if row else None

    def list_pending(self) -> list[ReviewItem]:
        rows = self._conn.execute(
            "SELECT id, run_id, thread_id, patient_id, reason, override_action, body, "
            "payload_json, status, created_at, updated_at FROM reviews "
            "WHERE status = 'pending' ORDER BY created_at ASC",
        ).fetchall()
        return [_item_from_row(row) for row in rows]

    def resolve(self, review_id: str, action: str) -> None:
        """Move a review to its terminal status. ``action`` is one of
        ``approve``, ``edit`` or ``decline``."""
        status = _TERMINAL_BY_ACTION.get(action)
        if status is None:
            raise ValueError(f"unknown review action: {action!r}")
        self._conn.execute(
            "UPDATE reviews SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), review_id),
        )
        self._conn.commit()
