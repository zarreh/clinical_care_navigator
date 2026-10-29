"""Read-write repository over runs.db — the operational record of every
conversation, persisted so a run replays from the store at any time, live or
long after it finished (docs/PLAN.md §7 Phase 6).

Unlike RecordStore/EducationStore/PolicyStore, this store creates its own schema
on first use: it holds operational state, not build-time data.
"""

from __future__ import annotations

from pathlib import Path

from zarreh_agentkit.runs import RunEventLog, utc_now

from navigator.store.models import RunRecord

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
"""


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
        conversation_id=str(row[9] if row[9] is not None else row[0]),
        turn=int(str(row[10] or 0)),
    )


_RUN_COLUMNS = (
    "id, question, patient_id, status, created_at, updated_at, answer_kind, answer_json, "
    "error, conversation_id, turn"
)


class RunStore(RunEventLog):
    """Persists conversation runs, their node-by-node events, and per-node LLM
    cost — the single source of truth ``GET /conversations/{id}`` and the SSE
    events endpoint read from."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path, table_prefix="conversation")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Adds the conversation columns to a database created before follow-ups
        existed, and gives every existing run its own one-turn conversation. Safe to
        run on every start."""
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(conversations)")}
        if "conversation_id" not in existing:
            self._conn.execute("ALTER TABLE conversations ADD COLUMN conversation_id TEXT")
        if "turn" not in existing:
            self._conn.execute(
                "ALTER TABLE conversations ADD COLUMN turn INTEGER NOT NULL DEFAULT 0"
            )
        self._conn.execute(
            "UPDATE conversations SET conversation_id = id WHERE conversation_id IS NULL"
        )
        # One run per (conversation, turn): two follow-ups to the same answer race on
        # this, and the loser's insert fails instead of forking the thread.
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_conversation_turn "
            "ON conversations (conversation_id, turn)"
        )

    def create_run(
        self,
        run_id: str,
        question: str,
        patient_id: str,
        *,
        conversation_id: str | None = None,
        turn: int = 0,
    ) -> None:
        """Starts a run. A follow-up passes the conversation it continues and its turn
        number; otherwise the run begins a new conversation. Raises
        ``sqlite3.IntegrityError`` if that turn of the conversation already exists."""
        now = utc_now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO conversations "
                "(id, question, patient_id, status, created_at, updated_at, conversation_id, turn) "
                "VALUES (?, ?, ?, 'running', ?, ?, ?, ?)",
                (run_id, question, patient_id, now, now, conversation_id or run_id, turn),
            )

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM conversations WHERE id = ?",  # noqa: S608 - fixed columns
            (run_id,),
        ).fetchone()
        return _run_from_row(row) if row else None

    def conversation_runs(self, conversation_id: str) -> list[RunRecord]:
        """Every turn of a conversation, oldest first."""
        rows = self._conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM conversations "  # noqa: S608 - fixed columns
            "WHERE conversation_id = ? ORDER BY turn ASC",
            (conversation_id,),
        ).fetchall()
        return [_run_from_row(row) for row in rows]

    def complete_run(self, run_id: str, status: str, answer_kind: str, answer_json: str) -> None:
        """Move a run to a terminal, answered state. ``status`` is one of
        ``answered``, ``templated`` or ``pending_review``; ``answer_kind`` names
        the payload shape (``published``/``templated``/``pending_review``)."""
        self._conn.execute(
            "UPDATE conversations SET status = ?, updated_at = ?, "
            "answer_kind = ?, answer_json = ? WHERE id = ?",
            (status, utc_now(), answer_kind, answer_json, run_id),
        )
        self._conn.commit()

    def fail_run(self, run_id: str, error: str) -> None:
        self._conn.execute(
            "UPDATE conversations SET status = 'failed', updated_at = ?, error = ? WHERE id = ?",
            (utc_now(), error, run_id),
        )
        self._conn.commit()

    def fail_interrupted_runs(
        self, error: str = "interrupted by a server restart before it finished"
    ) -> int:
        """Mark every ``running`` run as failed. Called once at startup: runs
        execute in-process, so any still ``running`` when the process starts were
        cut off by a restart and will never finish. Returns the number marked."""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE conversations SET status = 'failed', updated_at = ?, error = ? "
                "WHERE status = 'running'",
                (utc_now(), error),
            )
        return cur.rowcount
