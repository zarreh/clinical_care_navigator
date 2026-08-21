"""Rendered notes: stable, honest, and carrying exactly one planted attack."""

from __future__ import annotations

from navigator.store import RecordStore
from tests.fixtures import FixtureStores

RENDERED_MARKER = "[Rendered from the structured record."


def test_every_note_declares_that_it_was_rendered(
    record_store: RecordStore, stores: FixtureStores
) -> None:
    """The honesty rule from §4.3, asserted rather than documented.

    Synthea has no notes. Composing them from the structured record is fine;
    letting a reader believe a clinician wrote them is not.
    """
    for patient_id in stores.patient_ids:
        for note in record_store.notes(patient_id):
            assert note.body.startswith(RENDERED_MARKER)


def test_the_injection_fixture_is_present_and_flagged(
    record_store: RecordStore, stores: FixtureStores
) -> None:
    """Canonical case 7 needs the attack to exist and to be findable by column.

    Flagging it in `fixture_kind` means a test can locate the planted note
    without string-matching note bodies — so the eval harness never has to know
    the payload text, and the payload can change without breaking the harness.
    """
    flagged = [
        note
        for patient_id in stores.patient_ids
        for note in record_store.notes(patient_id)
        if note.fixture_kind is not None
    ]
    assert len(flagged) == 1
    assert flagged[0].fixture_kind == "indirect_prompt_injection"
    assert "ignore prior instructions" in flagged[0].body.lower()


def test_no_unflagged_note_contains_the_payload(
    record_store: RecordStore, stores: FixtureStores
) -> None:
    """A stray copy would make a case-7 failure ambiguous."""
    for patient_id in stores.patient_ids:
        for note in record_store.notes(patient_id):
            if note.fixture_kind is None:
                assert "ignore prior instructions" not in note.body.lower()
