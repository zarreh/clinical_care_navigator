"""Provenance tests — the ones the launch gate turns into conditions.

Gate §11.8 requires that every reference-range row and every red-flag rule cites
its source and that the build fails if not. These assert the same thing at test
time, offline, so the failure arrives in a pull request rather than in a data
rebuild.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from data.generate_policy_rules import ESCALATING_ACTIONS, RULES, validate

RANGES_CSV = Path(__file__).resolve().parents[2] / "data" / "lab_reference_ranges.csv"


def _range_rows() -> list[dict[str, str]]:
    with RANGES_CSV.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_every_reference_band_cites_and_quotes_a_source() -> None:
    for row in _range_rows():
        assert row["reference_source_url"].startswith("https://"), row["loinc_code"]
        assert row["reference_source_quote"].strip(), row["loinc_code"]
        assert row["reference_source_name"].strip(), row["loinc_code"]


def test_every_critical_band_cites_and_quotes_a_source() -> None:
    """A critical band decides whether someone is sent to emergency care.

    An uncited one is worse than an absent one, so the table is allowed to leave
    the band empty and is not allowed to assert it without a source.
    """
    for row in _range_rows():
        if not (row["critical_low"] or row["critical_high"]):
            continue
        assert row["critical_source_url"].startswith("https://"), row["loinc_code"]
        assert row["critical_source_quote"].strip(), row["loinc_code"]


def test_reference_bands_are_ordered_and_wider_than_critical_bands() -> None:
    for row in _range_rows():
        low = float(row["reference_low"]) if row["reference_low"] else None
        high = float(row["reference_high"]) if row["reference_high"] else None
        if low is not None and high is not None:
            assert low < high, row["loinc_code"]
        critical_high = float(row["critical_high"]) if row["critical_high"] else None
        if high is not None and critical_high is not None:
            assert critical_high > high, row["loinc_code"]
        critical_low = float(row["critical_low"]) if row["critical_low"] else None
        if low is not None and critical_low is not None:
            assert critical_low < low, row["loinc_code"]


def test_every_escalation_rule_cites_and_quotes_a_published_source() -> None:
    for rule in RULES:
        if rule.action not in ESCALATING_ACTIONS:
            continue
        assert rule.source_url and rule.source_url.startswith("https://"), rule.rule_id
        assert rule.source_quote and rule.source_quote.strip(), rule.rule_id


def test_rule_table_validation_rejects_an_uncited_escalation_rule() -> None:
    """The guard is real, not decorative."""
    from dataclasses import replace

    uncited = replace(RULES[0], rule_id="rf-uncited", source_url=None, source_quote=None)
    with pytest.raises(SystemExit, match="cite and quote"):
        validate((uncited,))


def test_scope_rules_do_not_borrow_clinical_authority() -> None:
    """A scope boundary is this project's decision, not a clinical finding.

    Attaching a MedlinePlus URL to "we do not give doses" would dress a product
    decision up as clinical guidance. The table keeps the difference visible.
    """
    for rule in RULES:
        if rule.action == "out_of_scope":
            assert rule.source_url is None, rule.rule_id


def test_the_build_rejects_an_uncited_reference_band(tmp_path: Path) -> None:
    """The fail-loud guard is real, not a comment in the docs."""
    import sqlite3

    from data.build_store import SCHEMA, insert_reference_ranges

    header = _range_rows()[0].keys()
    bad = dict.fromkeys(header, "")
    bad["loinc_code"] = "1234-5"
    bad["analyte"] = "Invented analyte"
    bad["specimen"] = "Serum or Plasma"
    bad["units"] = "mg/dL"
    bad["reference_low"] = "1"
    bad["reference_high"] = "2"
    bad["population"] = "adult-general"

    path = tmp_path / "bad_ranges.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        writer.writeheader()
        writer.writerow(bad)

    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    with pytest.raises(SystemExit, match="no cited source"):
        insert_reference_ranges(connection, path)


def test_the_build_rejects_an_uncited_critical_band(tmp_path: Path) -> None:
    """A critical band decides whether someone is told to seek emergency care."""
    import sqlite3

    from data.build_store import SCHEMA, insert_reference_ranges

    row = dict(_range_rows()[0])
    row["critical_source_url"] = ""
    row["critical_source_quote"] = ""
    row["critical_source_name"] = ""

    path = tmp_path / "uncited_critical.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    with pytest.raises(SystemExit, match="critical band"):
        insert_reference_ranges(connection, path)
