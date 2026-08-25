"""Falsifiable PHI-redaction test at the log boundary (docs/PLAN.md §5.7).

The assertion is made against the store's *own* patient values — names, birth
dates, identifiers actually present in the fixture — not against a regex guess.
A redactor that did nothing would fail: the control test proves the same log
call leaks those identifiers when the redactor is absent, so this is not a
vacuous check.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from navigator.guardrails.redaction import PhiRedactor
from navigator.observability import configure_logging, get_logger
from navigator.store import RecordStore
from tests.fixtures import build_fixture_stores

_MIN = 3


def _store_identifiers(store: RecordStore) -> list[str]:
    values: list[str] = []
    for pid in store.patient_ids():
        patient = store.get_patient(pid)
        assert patient is not None
        values.extend(
            (patient.given_name, patient.family_name, patient.birth_date, patient.patient_id)
        )
    return [v for v in values if v and len(v) >= _MIN]


def _log_line_with(identifiers: list[str], redactor: PhiRedactor | None) -> str:
    configure_logging("production", redactor=redactor)
    logger = get_logger("redaction-test")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        logger.info(
            "patient_event",
            patient=identifiers[0],
            note=f"seen {' '.join(identifiers[:8])}",
            nested={"who": identifiers[0], "list": identifiers[:4]},
        )
    return buffer.getvalue()


def test_redaction_removes_every_store_identifier(tmp_path: Path) -> None:
    stores = build_fixture_stores(tmp_path)
    store = RecordStore(stores.records_db)
    identifiers = _store_identifiers(store)
    assert identifiers, "fixture must expose patient identifiers to redact"
    redactor = PhiRedactor.from_patients(
        [p for p in (store.get_patient(i) for i in store.patient_ids()) if p is not None]
    )

    output = _log_line_with(identifiers, redactor).lower()
    for value in identifiers:
        assert value.lower() not in output, f"identifier leaked into log: {value!r}"

    # Restore a benign config for the rest of the suite.
    configure_logging("development")


def test_redaction_is_falsifiable(tmp_path: Path) -> None:
    stores = build_fixture_stores(tmp_path)
    store = RecordStore(stores.records_db)
    identifiers = _store_identifiers(store)

    # Same log call, no redactor installed: the identifier must survive, proving
    # the control test above would fail if redaction were a no-op.
    leaked = _log_line_with(identifiers, None).lower()
    assert identifiers[0].lower() in leaked

    configure_logging("development")
