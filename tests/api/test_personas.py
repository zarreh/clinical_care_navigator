"""Demonstration personas: who a visitor can ask as.

The selection runs on a purpose-built store so each rule is pinned precisely:
the richest record wins the "full record" role, roles tied to planted data are
filled by whoever the data planted them on, literacy and language roles pick the
richest *other* matching patient, and the API only answers as a persona.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from data.build_store import SCHEMA
from navigator.api import deps
from navigator.api.main import app
from navigator.api.personas import display_name, select_personas
from navigator.store import RecordStore
from navigator.store.models import Patient
from tests.api._navigator_client import NavigatorTestContext, build_navigator_test_context
from tests.fixtures import build_fixture_stores

TODAY = date(2026, 1, 1)
POTASSIUM = "2823-3"


def _patient(
    c: sqlite3.Connection, pid: str, *, lang: str = "en", literacy: str = "proficient"
) -> None:
    c.execute(
        "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?, ?)",
        (pid, f"Given{pid}7", f"Family{pid}42", "1950-06-15", "F", lang, literacy),
    )


def _labs(c: sqlite3.Connection, pid: str, n: int, *, a1c: bool = True) -> None:
    for i in range(n):
        name, loinc, value = (
            ("Hemoglobin A1c/Hemoglobin.total in Blood", "4548-4", 6.0 + i / 100)
            if a1c and i == 0
            else (f"Analyte {i % 5}", f"9{i % 5}", 1.0)
        )
        c.execute(
            "INSERT INTO observations VALUES "
            "(?, ?, 'e', ?, 'laboratory', ?, ?, ?, NULL, 'u', 'numeric')",
            (f"{pid}-o{i}", pid, f"2025-01-{(i % 27) + 1:02d}", loinc, name, value),
        )


def _more(c: sqlite3.Connection, pid: str, meds: int, conditions: int) -> None:
    for i in range(meds):
        c.execute(
            "INSERT INTO medications VALUES (?, ?, 'e', '2024-01-01', NULL, '1', ?, NULL)",
            (f"{pid}-m{i}", pid, f"Med {i}"),
        )
    for i in range(conditions):
        c.execute(
            "INSERT INTO conditions VALUES (?, ?, 'e', '2020-01-01', NULL, '1', ?)",
            (f"{pid}-c{i}", pid, f"Condition {i}"),
        )


@pytest.fixture
def store(tmp_path: Path) -> RecordStore:
    db = tmp_path / "records.db"
    c = sqlite3.connect(db)
    c.executescript(SCHEMA)
    c.execute(
        "INSERT INTO reference_ranges (loinc_code, analyte, specimen, units, reference_low, "
        "reference_high, reference_source_name, reference_source_url, reference_source_quote, "
        "critical_low, critical_high, critical_source_name, critical_source_url, "
        "critical_source_quote, population) VALUES (?, 'Potassium', 'serum', 'mmol/L', 3.5, 5.1, "
        "'s', 'u', 'q', 2.5, 6.0, 's', 'u', 'q', 'adult')",
        (POTASSIUM,),
    )
    # rich: the richest record overall (also basic literacy, to test role ordering)
    _patient(c, "rich", literacy="basic")
    _labs(c, "rich", 60)
    _more(c, "rich", 20, 10)
    # mid-basic: the richest *other* basic-literacy patient
    _patient(c, "midbasic", literacy="basic")
    _labs(c, "midbasic", 30)
    _more(c, "midbasic", 5, 4)
    # es: Spanish speaker
    _patient(c, "es", lang="es")
    _labs(c, "es", 25)
    _more(c, "es", 3, 3)
    # planted critical potassium, with a thin history
    _patient(c, "crit")
    _labs(c, "crit", 5)
    c.execute(
        "INSERT INTO observations VALUES ('crit-k', 'crit', 'e', '2025-12-30', 'laboratory', ?, "
        "'Potassium', 6.9, NULL, 'mmol/L', 'numeric')",
        (POTASSIUM,),
    )
    # planted injection note
    _patient(c, "inj")
    _labs(c, "inj", 8)
    c.execute(
        "INSERT INTO clinical_notes VALUES ('n1', 'inj', 'e', '2025-01-01', 'progress', 'b', "
        "'indirect_prompt_injection')"
    )
    # no A1c at all: never a persona for the A1c-based roles
    _patient(c, "noa1c")
    _labs(c, "noa1c", 40, a1c=False)
    c.commit()
    c.close()
    return RecordStore(db)


def test_each_role_picks_the_right_patient(store: RecordStore) -> None:
    by_role = {p.role: p for p in select_personas(store, today=TODAY)}

    assert by_role["full-record"].patient_id == "rich"
    assert by_role["critical-potassium"].patient_id == "crit"
    assert by_role["visit-note-injection"].patient_id == "inj"
    # "rich" is basic-literacy too, but the full-record role claimed it first, so the
    # literacy role gets the richest *other* basic patient rather than duplicating it.
    assert by_role["basic-literacy"].patient_id == "midbasic"
    assert by_role["spanish-speaker"].patient_id == "es"
    assert len({p.patient_id for p in by_role.values()}) == len(by_role)


def test_full_record_persona_is_listed_first_and_is_the_richest(store: RecordStore) -> None:
    personas = select_personas(store, today=TODAY)
    richest = max(personas, key=lambda p: p.history.richness)
    assert personas[0].role == "full-record"
    assert personas[0].patient_id == richest.patient_id


def test_a_patient_without_an_a1c_never_fills_an_a1c_role(store: RecordStore) -> None:
    ids = {p.patient_id for p in select_personas(store, today=TODAY)}
    assert "noa1c" not in ids  # rich in labs, but cannot demonstrate the A1c scenarios


def test_persona_carries_cleaned_name_age_and_history_counts(store: RecordStore) -> None:
    persona = next(p for p in select_personas(store, today=TODAY) if p.patient_id == "rich")

    assert persona.name == "Givenrich Familyrich"  # Synthea's trailing digits removed
    assert persona.age == 75  # born 1950-06-15, "today" 2026-01-01
    assert (persona.history.labs, persona.history.medications, persona.history.conditions) == (
        60,
        20,
        10,
    )


def test_selection_is_stable_between_runs(store: RecordStore) -> None:
    first = [p.patient_id for p in select_personas(store, today=TODAY)]
    assert first == [p.patient_id for p in select_personas(store, today=TODAY)]


def test_a_small_store_is_topped_up_so_it_is_never_empty(tmp_path: Path) -> None:
    stores = build_fixture_stores(tmp_path)
    personas = select_personas(RecordStore(stores.records_db), today=TODAY)
    assert {p.patient_id for p in personas} == set(stores.patient_ids)


def test_display_name_strips_digits_but_keeps_names() -> None:
    patient = Patient("x", "Aaron697", "O'Conner864", "1980-01-01", "M", "en", "basic")
    assert display_name(patient) == "Aaron O'Conner"
    assert display_name(Patient("x", "123", "456", "1980-01-01", "M", "en", "basic")) == (
        "Demo patient"
    )


# --- the API ---------------------------------------------------------------


def test_personas_endpoint_lists_the_selection(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    body = ctx.client.get("/personas").json()

    assert {p["patient_id"] for p in body} == set(ctx.record_store.patient_ids())
    assert {"patient_id", "name", "age", "language", "literacy", "headline", "blurb"} <= set(
        body[0]
    )
    assert set(body[0]["history"]) == {
        "labs",
        "analytes",
        "medications",
        "conditions",
        "encounters",
        "notes",
    }


def test_a_conversation_defaults_to_the_first_persona(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    first = ctx.client.get("/personas").json()[0]["patient_id"]

    run_id = ctx.client.post("/conversations", json={"question": "Explain my A1c"}).json()["id"]

    assert ctx.client.get(f"/conversations/{run_id}").json()["patient_id"] == first


def _add_non_persona_patient(ctx: NavigatorTestContext) -> str:
    """A real patient in the store who was not selected as a persona. The selection is
    cached per store instance, so a row added after the first GET /personas stays out."""
    ctx.client.get("/personas")
    extra = "someone-else"
    conn = sqlite3.connect(ctx.settings.record_db_path)
    conn.execute(
        "INSERT INTO patients VALUES (?, 'Extra', 'Person', '1990-01-01', 'F', 'en', 'basic')",
        (extra,),
    )
    conn.commit()
    conn.close()
    return extra


def test_the_api_refuses_a_real_patient_that_is_not_a_persona(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    extra = _add_non_persona_patient(ctx)
    assert ctx.record_store.get_patient(extra) is not None

    resp = ctx.client.post("/conversations", json={"question": "q", "patient_id": extra})

    assert resp.status_code == 404
    assert "demo personas" in resp.json()["detail"]


def test_the_restriction_can_be_turned_off(tmp_path: Path) -> None:
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    extra = _add_non_persona_patient(ctx)
    relaxed = ctx.settings.model_copy(update={"demo_patients_only": False})
    app.dependency_overrides[deps.settings_dependency] = lambda: relaxed

    resp = ctx.client.post("/conversations", json={"question": "q", "patient_id": extra})

    assert resp.status_code == 202
