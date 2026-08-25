"""Post-flight check 1: the critical-value scan (§5.3, canonical case 4)."""

from __future__ import annotations

from navigator.guardrails.critical_values import (
    CRITICAL_VALUE_ACTION,
    scan_critical_values,
)
from navigator.schemas.scoping import EvidenceRecord
from navigator.store.record_store import RecordStore

# Potassium: reference 3.7–5.2, critical_high 6.0, critical_low 2.5 (§ fixture).
_POTASSIUM = "2823-3"


def _labs_evidence(loinc: str, value: float, *, call_id: str = "call-1") -> EvidenceRecord:
    return EvidenceRecord(
        tool_call_id=call_id,
        tool_name="get_labs",
        args_after_scoping={"patient_id": "p", "loinc_code": loinc},
        result={
            "patient_id": "p",
            "count": 1,
            "labs": [{"loinc_code": loinc, "value_number": value, "units": "mmol/L"}],
        },
        retrieved_at="2026-08-20T00:00:00+00:00",
    )


def test_critical_high_potassium_fires_with_citation(record_store: RecordStore) -> None:
    # Case 4's injected value: a benign question, but the value itself is critical.
    findings = scan_critical_values([_labs_evidence(_POTASSIUM, 6.9)], record_store.reference_range)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.analyte == "Potassium"
    assert finding.band == "critical_high"
    assert finding.threshold == 6.0
    assert finding.value == 6.9
    assert finding.action == CRITICAL_VALUE_ACTION == "direct_to_emergency_care"
    # The escalation shows its published basis, not a bare number.
    assert finding.source_url is not None
    assert finding.source_quote is not None


def test_critical_low_potassium_fires(record_store: RecordStore) -> None:
    findings = scan_critical_values([_labs_evidence(_POTASSIUM, 2.0)], record_store.reference_range)
    assert len(findings) == 1
    assert findings[0].band == "critical_low"
    assert findings[0].threshold == 2.5


def test_benign_value_does_not_fire(record_store: RecordStore) -> None:
    findings = scan_critical_values([_labs_evidence(_POTASSIUM, 4.5)], record_store.reference_range)
    assert findings == []


def test_boundary_value_at_threshold_fires(record_store: RecordStore) -> None:
    # >= critical_high is critical: the threshold itself is in the band.
    findings = scan_critical_values([_labs_evidence(_POTASSIUM, 6.0)], record_store.reference_range)
    assert len(findings) == 1
    assert findings[0].band == "critical_high"


def test_unknown_loinc_is_skipped(record_store: RecordStore) -> None:
    findings = scan_critical_values(
        [_labs_evidence("99999-9", 999.0)], record_store.reference_range
    )
    assert findings == []


def test_missing_value_is_skipped(record_store: RecordStore) -> None:
    evidence = EvidenceRecord(
        tool_call_id="c",
        tool_name="get_labs",
        args_after_scoping={},
        result={"labs": [{"loinc_code": _POTASSIUM, "value_number": None, "units": "mmol/L"}]},
        retrieved_at="2026-08-20T00:00:00+00:00",
    )
    assert scan_critical_values([evidence], record_store.reference_range) == []


def test_non_labs_evidence_is_ignored(record_store: RecordStore) -> None:
    # An education result has no `labs` key: the scan simply skips it.
    education = EvidenceRecord(
        tool_call_id="c",
        tool_name="lookup_lab_education",
        args_after_scoping={},
        result={"code_system": "LOINC", "code": _POTASSIUM, "pages": [], "gap_declared": True},
        retrieved_at="2026-08-20T00:00:00+00:00",
    )
    assert scan_critical_values([education], record_store.reference_range) == []
