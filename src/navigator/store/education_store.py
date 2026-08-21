"""Read-only repository over the fetched education corpus.

Exact lookup, not similarity search: a LOINC code or an RxCUI is joined to the
page MedlinePlus Connect returned for exactly that code (D-A3-5). Searching
semantically for "Hemoglobin A1c" when the observation already carries LOINC
`4548-4` would substitute a probabilistic match for an exact one in the single
place where being wrong is expensive.

`lookup` returning an empty list is a **declared gap**, not a failure to try
harder. The caller says the system has no vetted education for that item and
routes; it never substitutes a similar test (docs/PLAN.md §4.2, case 14).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from navigator.store.models import CoverageGap, EducationPage

_PAGE_COLUMNS = "code_system, code, title, url, summary_html, attribution, retrieved_at"
_GAP_COLUMNS = "code_system, code, label, checked_at"


class EducationStore:
    """Exact-lookup access to `education.db`."""

    def __init__(self, db_path: Path) -> None:
        self._connection = sqlite3.connect(db_path, check_same_thread=False)

    def close(self) -> None:
        self._connection.close()

    def lookup(self, code_system: str, code: str, *, limit: int = 3) -> list[EducationPage]:
        rows = self._connection.execute(
            f"SELECT {_PAGE_COLUMNS} FROM education_pages WHERE code_system = ? AND code = ? "
            "ORDER BY title ASC LIMIT ?",
            (code_system, code, limit),
        ).fetchall()
        return [EducationPage(*row) for row in rows]

    def for_loinc(self, loinc_code: str, *, limit: int = 3) -> list[EducationPage]:
        return self.lookup("loinc", loinc_code, limit=limit)

    def for_rxcui(self, rxcui: str, *, limit: int = 3) -> list[EducationPage]:
        return self.lookup("rxcui", rxcui, limit=limit)

    def gap(self, code_system: str, code: str) -> CoverageGap | None:
        row = self._connection.execute(
            f"SELECT {_GAP_COLUMNS} FROM coverage_gaps WHERE code_system = ? AND code = ?",
            (code_system, code),
        ).fetchone()
        return CoverageGap(*row) if row else None

    def gaps(self) -> list[CoverageGap]:
        rows = self._connection.execute(
            f"SELECT {_GAP_COLUMNS} FROM coverage_gaps ORDER BY code_system ASC, code ASC"
        ).fetchall()
        return [CoverageGap(*row) for row in rows]

    def citation_urls(self) -> list[str]:
        """Every distinct URL the corpus can emit — the reachability metric's input."""
        return [
            str(row[0])
            for row in self._connection.execute(
                "SELECT DISTINCT url FROM education_pages ORDER BY url"
            )
        ]

    def coverage(self, code_system: str) -> tuple[int, int]:
        """(covered, gaps) for one code system."""
        covered = self._connection.execute(
            "SELECT COUNT(DISTINCT code) FROM education_pages WHERE code_system = ?",
            (code_system,),
        ).fetchone()[0]
        gaps = self._connection.execute(
            "SELECT COUNT(*) FROM coverage_gaps WHERE code_system = ?", (code_system,)
        ).fetchone()[0]
        return int(covered), int(gaps)
