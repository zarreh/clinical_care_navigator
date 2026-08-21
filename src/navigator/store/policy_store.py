"""Read-only repository over the editable safety rule table.

Policy lives in a table the clinical owner can edit without a deploy — the
source notebook's best idea, kept (docs/PLAN.md §3.8) — with a version column
added, so a decision can name the rule table it was made under.

This store hands out rule *rows*. Compiling them into matchers, with the
negation and attribution handling that keeps canonical case 12 from escalating,
is `guardrails/rule_engine.py`'s job in Phase 3.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from navigator.store.models import PolicyRule

_RULE_COLUMNS = (
    "rule_id, action, band, category, pattern, description, template_id, severity, "
    "source_name, source_url, source_quote, version, enabled"
)


def _to_rule(row: tuple[object, ...]) -> PolicyRule:
    values = list(row)
    values[12] = bool(values[12])
    return PolicyRule(*values)  # type: ignore[arg-type]


class PolicyStore:
    """Read access to `policy.db`."""

    def __init__(self, db_path: Path) -> None:
        self._connection = sqlite3.connect(db_path, check_same_thread=False)

    def close(self) -> None:
        self._connection.close()

    def enabled_rules(self) -> list[PolicyRule]:
        rows = self._connection.execute(
            f"SELECT {_RULE_COLUMNS} FROM policy_rules WHERE enabled = 1 "
            "ORDER BY severity DESC, rule_id ASC"
        ).fetchall()
        return [_to_rule(row) for row in rows]

    def rule(self, rule_id: str) -> PolicyRule | None:
        row = self._connection.execute(
            f"SELECT {_RULE_COLUMNS} FROM policy_rules WHERE rule_id = ?", (rule_id,)
        ).fetchone()
        return _to_rule(row) if row else None

    def table_version(self) -> int:
        row = self._connection.execute("SELECT MAX(version) FROM policy_rules").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
