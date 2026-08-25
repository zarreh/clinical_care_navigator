"""Read-write repository over runs.db — the operational record of every
conversation, persisted so a run replays from the store at any time, live or
long after it finished (docs/PLAN.md §7 Phase 6).

Unlike RecordStore/EducationStore/PolicyStore, this store creates its own schema
on first use: it holds operational state, not build-time data.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from navigator.store.models import CostEntry, RunEvent, RunRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    answer_kind TEXT,
    answer_json TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS conversation_events (
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    node TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, sequence)
);
CREATE TABLE IF NOT EXISTS conversation_costs (
    run_id TEXT NOT NULL,
    node TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run_from_row(row: tuple[object, ...]) -> RunRecord:
    return RunRecord(
        id=str(row[0]),
        question=str(row[1]),
        patient_id=str(row[2]),
        status=str(row[3]),
        created_at=str(row[4]),
        updated_at=str(row[5]),
        answer_kind=None if row[6] is None else str(row[6]),
        answer_json=None if row[7] is None else str(row[7]),
        error=None if row[8] is None else str(row[8]),
    )


class RunStore:
    """Persists conversation runs, their node-by-node events, and per-node LLM
    cost — the single source of truth ``GET /conversations/{id}`` and the SSE
    events endpoint read from."""

    def __init__(self, db_path: Path) -> None:
        # check_same_thread=False: FastAPI handles requests and the background
        # run executor from different threads/tasks against one connection.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_run(self, run_id: str, question: str, patient_id: str) -> None:
        now = _now()
        self._conn.execute(
            "INSERT INTO conversations "
            "(id, question, patient_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'running', ?, ?)",
            (run_id, question, patient_id, now, now),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._conn.execute(
            "SELECT id, question, patient_id, status, created_at, updated_at, "
            "answer_kind, answer_json, error FROM conversations WHERE id = ?",
            (run_id,),
        ).fetchone()
        return _run_from_row(row) if row else None

    def complete_run(self, run_id: str, status: str, answer_kind: str, answer_json: str) -> None:
        """Move a run to a terminal, answered state. ``status`` is one of
        ``answered``, ``templated`` or ``pending_review``; ``answer_kind`` names
        the payload shape (``published``/``templated``/``pending_review``)."""
        self._conn.execute(
            "UPDATE conversations SET status = ?, updated_at = ?, "
            "answer_kind = ?, answer_json = ? WHERE id = ?",
            (status, _now(), answer_kind, answer_json, run_id),
        )
        self._conn.commit()

    def fail_run(self, run_id: str, error: str) -> None:
        self._conn.execute(
            "UPDATE conversations SET status = 'failed', updated_at = ?, error = ? WHERE id = ?",
            (_now(), error, run_id),
        )
        self._conn.commit()

    def append_event(self, run_id: str, sequence: int, node: str, payload_json: str) -> None:
        self._conn.execute(
            "INSERT INTO conversation_events (run_id, sequence, node, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, sequence, node, payload_json, _now()),
        )
        self._conn.commit()

    def get_events(self, run_id: str, after_sequence: int = -1) -> list[RunEvent]:
        """Every event with ``sequence > after_sequence``, in order — the same
        call replays a whole run from the start (default) or tails new events
        since the last one a client already saw."""
        rows = self._conn.execute(
            "SELECT run_id, sequence, node, payload_json, created_at FROM conversation_events "
            "WHERE run_id = ? AND sequence > ? ORDER BY sequence",
            (run_id, after_sequence),
        ).fetchall()
        return [
            RunEvent(
                run_id=str(row[0]),
                sequence=int(row[1]),
                node=str(row[2]),
                payload_json=str(row[3]),
                created_at=str(row[4]),
            )
            for row in rows
        ]

    def record_costs(self, run_id: str, entries: list[CostEntry]) -> None:
        self._conn.executemany(
            "INSERT INTO conversation_costs "
            "(run_id, node, model, prompt_tokens, completion_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (run_id, e.node, e.model, e.prompt_tokens, e.completion_tokens, e.cost_usd)
                for e in entries
            ],
        )
        self._conn.commit()

    def get_costs(self, run_id: str) -> list[CostEntry]:
        rows = self._conn.execute(
            "SELECT node, model, prompt_tokens, completion_tokens, cost_usd "
            "FROM conversation_costs WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        return [
            CostEntry(
                node=str(row[0]),
                model=str(row[1]),
                prompt_tokens=int(row[2]),
                completion_tokens=int(row[3]),
                cost_usd=float(row[4]),
            )
            for row in rows
        ]
