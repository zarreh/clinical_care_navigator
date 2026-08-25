"""Every tool runs with no LLM and no network (docs/PLAN.md Phase 2 exit).

Each tool is invoked directly against the offline fixture stores and asserted to
return its typed Pydantic envelope. A missing patient, an empty list and a
declared coverage gap are all first-class results, never exceptions.
"""

from __future__ import annotations

import pytest

from navigator.schemas.tools import (
    ClinicalNotesResult,
    ConditionsResult,
    EducationResult,
    EncountersResult,
    LabsResult,
    MedicationsResult,
    PatientProfileResult,
    ProceduresResult,
    ReferenceRangeResult,
)
from navigator.tools import ToolRegistry

# Codes present in the committed fixture seed.
LOINC_WITH_EDUCATION = "18262-6"
LOINC_WITH_RANGE = "2823-3"
RXCUI_WITH_EDUCATION = "310798"
UNCOVERED_LOINC = "99999-9"
UNCOVERED_RXCUI = "00000"


def _invoke(registry: ToolRegistry, name: str, **args: object) -> object:
    return registry.tools[name].invoke(dict(args))


def test_registry_exposes_exactly_eleven_tools(registry: ToolRegistry) -> None:
    assert len(registry.tools) == 11


def test_get_patient_profile_returns_profile(
    registry: ToolRegistry, patient_ids: list[str]
) -> None:
    result = _invoke(registry, "get_patient_profile", patient_id=patient_ids[0])
    assert isinstance(result, PatientProfileResult)
    assert result.found
    assert result.profile is not None
    assert result.profile.patient_id == patient_ids[0]
    assert result.profile.health_literacy_level in {"basic", "intermediate", "proficient"}


def test_get_patient_profile_missing_patient_is_not_found(registry: ToolRegistry) -> None:
    result = _invoke(registry, "get_patient_profile", patient_id="no-such-patient")
    assert isinstance(result, PatientProfileResult)
    assert not result.found
    assert result.profile is None


def test_list_patient_encounters(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "list_patient_encounters", patient_id=patient_ids[0])
    assert isinstance(result, EncountersResult)
    assert result.count == len(result.encounters)


def test_get_labs_exact_loinc_filter(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_labs", patient_id=patient_ids[0], loinc_code=LOINC_WITH_RANGE)
    assert isinstance(result, LabsResult)
    assert all(lab.loinc_code == LOINC_WITH_RANGE for lab in result.labs)


def test_get_medications_carry_rxcui(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_medications", patient_id=patient_ids[0])
    assert isinstance(result, MedicationsResult)
    assert all(med.rxcui for med in result.medications)


def test_get_conditions(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_conditions", patient_id=patient_ids[0])
    assert isinstance(result, ConditionsResult)
    assert result.count == len(result.conditions)


def test_get_procedures(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_procedures", patient_id=patient_ids[0])
    assert isinstance(result, ProceduresResult)
    assert result.count == len(result.procedures)


def test_get_allergies_empty_list_is_valid(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_allergies", patient_id=patient_ids[0])
    # The sample cohort records no allergies; an empty list is a meaningful,
    # non-error answer.
    assert result.count == len(result.allergies)  # type: ignore[attr-defined]


def test_get_clinical_notes_are_rendered(registry: ToolRegistry, patient_ids: list[str]) -> None:
    result = _invoke(registry, "get_clinical_notes", patient_id=patient_ids[0])
    assert isinstance(result, ClinicalNotesResult)
    assert result.count == len(result.notes)


def test_lookup_lab_education_resolves_and_cites(registry: ToolRegistry) -> None:
    result = _invoke(registry, "lookup_lab_education", loinc_code=LOINC_WITH_EDUCATION)
    assert isinstance(result, EducationResult)
    assert not result.gap_declared
    assert result.pages
    assert all(page.url.startswith("https://") for page in result.pages)
    assert all(page.attribution for page in result.pages)


def test_lookup_lab_education_declares_gap_for_uncovered_code(registry: ToolRegistry) -> None:
    result = _invoke(registry, "lookup_lab_education", loinc_code=UNCOVERED_LOINC)
    assert isinstance(result, EducationResult)
    assert result.gap_declared
    assert result.pages == []


def test_lookup_medication_education_resolves(registry: ToolRegistry) -> None:
    result = _invoke(registry, "lookup_medication_education", rxcui=RXCUI_WITH_EDUCATION)
    assert isinstance(result, EducationResult)
    assert not result.gap_declared
    assert result.pages


def test_lookup_medication_education_declares_gap(registry: ToolRegistry) -> None:
    result = _invoke(registry, "lookup_medication_education", rxcui=UNCOVERED_RXCUI)
    assert isinstance(result, EducationResult)
    assert result.gap_declared


def test_reference_range_found_carries_quote(registry: ToolRegistry) -> None:
    result = _invoke(registry, "get_lab_reference_range", loinc_code=LOINC_WITH_RANGE)
    assert isinstance(result, ReferenceRangeResult)
    assert result.found
    assert result.band is not None
    assert result.band.reference_source_quote
    assert result.band.reference_source_url.startswith("https://")


def test_reference_range_missing_is_not_estimated(registry: ToolRegistry) -> None:
    result = _invoke(registry, "get_lab_reference_range", loinc_code=UNCOVERED_LOINC)
    assert isinstance(result, ReferenceRangeResult)
    assert not result.found
    assert result.band is None


@pytest.mark.parametrize(
    "name",
    [
        "get_patient_profile",
        "list_patient_encounters",
        "get_labs",
        "get_medications",
        "get_conditions",
        "get_procedures",
        "get_allergies",
        "get_clinical_notes",
    ],
)
def test_patient_tools_declare_patient_id_argument(registry: ToolRegistry, name: str) -> None:
    assert "patient_id" in registry.tools[name].args
