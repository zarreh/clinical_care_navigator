"""Record store behaviour, including the two properties that are security controls."""

from __future__ import annotations

from navigator.store import DEFAULT_ROW_CAP, RecordStore
from tests.fixtures import FixtureStores


def test_reads_are_capped_even_when_a_caller_asks_for_more(record_store: RecordStore) -> None:
    """The cap is minimum-necessary enforcement, so it cannot be argued away.

    45 CFR 164.502(b) is not satisfied by a caller that remembers to pass a
    limit; it is satisfied by a store that cannot return more than one.
    """
    patient_id = record_store.patient_ids()[0]
    observations = record_store.observations(patient_id, limit=10_000)
    assert len(observations) <= DEFAULT_ROW_CAP


def test_a_caller_may_ask_for_less_than_the_cap(record_store: RecordStore) -> None:
    patient_id = record_store.patient_ids()[0]
    assert len(record_store.observations(patient_id, limit=3)) <= 3


def test_every_row_returned_belongs_to_the_requested_patient(
    record_store: RecordStore, stores: FixtureStores
) -> None:
    first, second = stores.patient_ids
    for patient_id in (first, second):
        for observation in record_store.observations(patient_id):
            assert observation.patient_id == patient_id
        for medication in record_store.medications(patient_id):
            assert medication.patient_id == patient_id
        for note in record_store.notes(patient_id):
            assert note.patient_id == patient_id


def test_an_unknown_patient_reads_nothing(record_store: RecordStore) -> None:
    assert record_store.get_patient("not-a-patient") is None
    assert record_store.observations("not-a-patient") == []


def test_reference_range_is_absent_rather_than_estimated(record_store: RecordStore) -> None:
    """A missing band is a first-class answer (§3.7)."""
    assert record_store.reference_range("99999-9") is None

    potassium = record_store.reference_range("2823-3")
    assert potassium is not None
    assert potassium.has_critical_band
    assert potassium.reference_source_quote
    assert potassium.critical_source_quote


def test_ranges_carry_the_quote_the_answer_will_show(record_store: RecordStore) -> None:
    for reference_range in record_store.reference_ranges():
        assert reference_range.reference_source_url.startswith("https://")
        assert reference_range.reference_source_quote.strip()
