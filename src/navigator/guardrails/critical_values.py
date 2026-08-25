"""Critical-value scan — post-flight check 1 (docs/PLAN.md §5.3).

This is the pure-code check that makes canonical case 4 work: a patient asks a
benign question ("what does my potassium result mean?"), the draft answers it
correctly and calmly, and *the retrieved value itself* is in a published panic
band. No amount of careful wording should let that answer publish unescalated —
so a deterministic scan over the recorded lab evidence, independent of the
question and the draft, forces escalation.

The scan is code, not a model call, for the same reason the pre-flight rule
screen is: a panic value is a fixed, published threshold, and a fixed threshold
deserves a deterministic check that cannot be talked out of firing. Each finding
carries the reference row's own citation and verbatim quote (D-A3-7), so the
escalation shows the reader the published sentence its threshold came from rather
than asserting a number.
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.schemas.postflight import CriticalFinding
from navigator.schemas.preflight import PolicyAction
from navigator.schemas.scoping import EvidenceRecord
from navigator.store.models import ReferenceRange

# The LOINC -> reference-range lookup the scan depends on. Passed as a callable
# (the node supplies `record_store.reference_range`) so this stays decoupled from
# the store: it depends only on the lookup, not on the repository type.
ReferenceRangeLookup = Callable[[str], ReferenceRange | None]

# A retrieved panic value is a medical emergency by definition — the published
# thresholds this project quotes describe values at which clinical manifestations
# appear — so the implied action is the emergency-care route, the most
# restrictive action there is (D-A3-7). Post-flight combines it with the
# pre-flight action via `more_restrictive`, so this can only escalate.
CRITICAL_VALUE_ACTION: PolicyAction = "direct_to_emergency_care"

# The get_labs tool's result envelope carries its rows under this key.
_LABS_KEY = "labs"


def _as_float(value: object) -> float | None:
    """Coerce a JSON-dumped numeric to float, or None if it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _classify(range_row: ReferenceRange, value: float) -> tuple[str, float] | None:
    """Return the crossed critical band and its threshold, or None.

    Checks the high band first, then the low band. A row with no critical band
    (the common case — only 8 of the curated rows have a citable panic value)
    can never fire, which is the point: critical bands exist only where a
    published threshold could be quoted.
    """
    if range_row.critical_high is not None and value >= range_row.critical_high:
        return "critical_high", range_row.critical_high
    if range_row.critical_low is not None and value <= range_row.critical_low:
        return "critical_low", range_row.critical_low
    return None


def scan_critical_values(
    evidence: list[EvidenceRecord],
    reference_range: ReferenceRangeLookup,
) -> list[CriticalFinding]:
    """Scan recorded lab evidence for values in a published critical band.

    `reference_range` is passed as a callable (the node supplies
    `record_store.reference_range`) so this stays decoupled from the store —
    it depends only on the LOINC → range lookup, not on the repository.

    A lab row fires a finding when its value crosses a critical threshold the
    reference row carries a citable quote for. Rows without a numeric value, an
    unknown LOINC, or a range with no critical band are skipped rather than
    guessed at.
    """
    findings: list[CriticalFinding] = []
    for record in evidence:
        rows = record.result.get(_LABS_KEY)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            loinc = row.get("loinc_code")
            value = _as_float(row.get("value_number"))
            if not isinstance(loinc, str) or value is None:
                continue
            range_row = reference_range(loinc)
            if range_row is None or not range_row.has_critical_band:
                continue
            crossed = _classify(range_row, value)
            if crossed is None:
                continue
            band, threshold = crossed
            units = row.get("units")
            findings.append(
                CriticalFinding(
                    loinc_code=loinc,
                    analyte=range_row.analyte,
                    value=value,
                    unit=units if isinstance(units, str) else range_row.units,
                    band=band,  # type: ignore[arg-type]
                    threshold=threshold,
                    action=CRITICAL_VALUE_ACTION,
                    source_name=range_row.critical_source_name,
                    source_url=range_row.critical_source_url,
                    source_quote=range_row.critical_source_quote,
                )
            )
    return findings
