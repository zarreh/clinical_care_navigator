"""Demonstration personas: the patients a visitor can ask as.

The app is a demo with no sign-in, so "who is asking?" has to be an explicit, safe
choice instead of an accident of which row comes first in the database. This
picks a short list of synthetic patients by *what their record can show off*,
ranked by how much history they have, and that list doubles as the allow-list of
patients the API will answer for.

Personas are chosen at runtime from the store (not hard-coded ids), so they stay
correct when the data is rebuilt. A role that the data cannot fill is simply
absent; the list is topped up with the richest remaining patients so it is never
empty for a non-empty store.

This is a demo selector, **not authentication**. Real use needs sign-in so the
server learns who the patient is, with the patient id taken from the session.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from navigator.store import RecordStore
from navigator.store.models import HistorySummary, Patient

_A1C = "hemoglobin A1c"
_POTASSIUM_LOINC = "2823-3"
_MIN_PERSONAS = 3
_MAX_PERSONAS = 6


@dataclass(frozen=True)
class Persona:
    patient_id: str
    role: str
    name: str
    age: int | None
    gender: str
    language: str
    literacy: str
    headline: str
    blurb: str
    history: HistorySummary


def display_name(patient: Patient) -> str:
    """Synthea appends digits to names ("Aaron697"); a person has none."""
    parts = [re.sub(r"\d+", "", patient.given_name), re.sub(r"\d+", "", patient.family_name)]
    return " ".join(part.strip() for part in parts if part.strip()) or "Demo patient"


def _age(birth_date: str, today: date) -> int | None:
    try:
        born = date.fromisoformat(birth_date[:10])
    except ValueError:
        return None
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _has_a1c(store: RecordStore, patient_id: str) -> bool:
    return any(
        o.value_number is not None for o in store.observations(patient_id, analyte=_A1C, limit=1)
    )


def _has_critical_potassium(store: RecordStore, patient_id: str) -> bool:
    band = store.reference_range(_POTASSIUM_LOINC)
    if band is None or band.critical_high is None:
        return False
    latest = store.observations(patient_id, loinc_code=_POTASSIUM_LOINC, limit=1)
    return bool(latest) and (latest[0].value_number or 0.0) >= band.critical_high


@dataclass(frozen=True)
class _Role:
    slug: str
    headline: str
    blurb: str
    matches: Callable[[RecordStore, Patient, HistorySummary], bool]


# Data-determined roles come first so that a patient the data *plants* a fact on
# is not consumed by a general role; the full record then claims the richest of the
# rest, so the literacy and language roles pick the richest *other* patient.
_ROLES: tuple[_Role, ...] = (
    _Role(
        "critical-potassium",
        "A hidden critical value",
        "Their record holds a critical potassium. Ask an ordinary lab question and watch "
        "post-flight override the draft.",
        lambda store, p, h: _has_critical_potassium(store, p.patient_id),
    ),
    _Role(
        "visit-note-injection",
        "A visit note with a planted instruction",
        "One visit note contains an instruction aimed at the AI. Ask for a summary of the "
        "visit to see it treated as data, not obeyed.",
        lambda store, p, h: h.injection_notes > 0,
    ),
    _Role(
        "full-record",
        "A full record",
        "The richest history in the data: many labs, medications and conditions to ask about.",
        lambda store, p, h: _has_a1c(store, p.patient_id),
    ),
    _Role(
        "basic-literacy",
        "Basic health literacy",
        "Answers are written at an easier reading level, and the measured grade is shown.",
        lambda store, p, h: p.health_literacy_level == "basic" and _has_a1c(store, p.patient_id),
    ),
    _Role(
        "spanish-speaker",
        "Spanish-speaking patient",
        "Their record language is Spanish. Ask in Spanish to see the stated-limitation reply.",
        lambda store, p, h: p.language != "en" and _has_a1c(store, p.patient_id),
    ),
)

_DISPLAY_ORDER = (
    "full-record",
    "critical-potassium",
    "basic-literacy",
    "spanish-speaker",
    "visit-note-injection",
)


def select_personas(store: RecordStore, *, today: date | None = None) -> list[Persona]:
    today = today or date.today()
    ranked = sorted(
        (store.history_summary(pid) for pid in store.patient_ids()),
        key=lambda s: (-s.richness, s.patient_id),
    )
    patients: dict[str, Patient] = {}
    for summary in ranked:
        patient = store.get_patient(summary.patient_id)
        if patient is not None:
            patients[summary.patient_id] = patient

    chosen: dict[str, tuple[_Role | None, HistorySummary]] = {}
    for role in _ROLES:
        for summary in ranked:
            patient = patients.get(summary.patient_id)
            if patient is None or summary.patient_id in chosen:
                continue
            if role.matches(store, patient, summary):
                chosen[summary.patient_id] = (role, summary)
                break

    # Top up so a store the roles cannot fill is still usable.
    for summary in ranked:
        if len(chosen) >= _MIN_PERSONAS:
            break
        if summary.patient_id in patients and summary.patient_id not in chosen:
            chosen[summary.patient_id] = (None, summary)

    order = {slug: i for i, slug in enumerate(_DISPLAY_ORDER)}
    items = sorted(
        chosen.items(),
        key=lambda kv: (
            order.get(kv[1][0].slug, len(order)) if kv[1][0] else len(order),
            -kv[1][1].richness,
            kv[0],
        ),
    )
    personas: list[Persona] = []
    for patient_id, (picked, summary) in items[:_MAX_PERSONAS]:
        patient = patients[patient_id]
        personas.append(
            Persona(
                patient_id=patient_id,
                role=picked.slug if picked else "demo-patient",
                name=display_name(patient),
                age=_age(patient.birth_date, today),
                gender=patient.gender,
                language=patient.language,
                literacy=patient.health_literacy_level,
                headline=picked.headline if picked else "A demo patient",
                blurb=picked.blurb if picked else "A synthetic patient with a real-looking record.",
                history=summary,
            )
        )
    return personas


@lru_cache(maxsize=8)
def personas_for(store: RecordStore) -> tuple[Persona, ...]:
    """Cached per store instance: selection scans every patient, so it runs once."""
    return tuple(select_personas(store))
