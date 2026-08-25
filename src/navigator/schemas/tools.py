"""Pydantic argument and result models for the eleven tools (docs/PLAN.md §3.6).

The source notebook's tools returned JSON **strings** the model had to re-parse,
and its "citations" were scraped back out of those strings with a bare
`except Exception: pass`. Here every tool has a typed argument schema and a typed
result model, so the boundary is checked in both directions and a result can be
addressed field by field rather than re-parsed.

Result models mirror the frozen store dataclasses but are Pydantic, because a
store row is an internal read model while a tool result is a boundary the agent
and the evidence log both consume. Education results carry their `url` and
`attribution` as first-class fields: the citation is the point of the app, not a
string to be recovered later.

A missing patient, an empty list and a declared coverage gap are all first-class
results, never errors and never a silently substituted near-match (§4.2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from navigator.schemas.common import LiteracyLevel

# --- arguments --------------------------------------------------------------
#
# `patient_id` on a patient-scoped tool is present in the schema so the model
# can be *told* the field exists, but the executor overwrites it with the
# session patient before the tool runs (docs/PLAN.md §3.4). It is never trusted.


class PatientIdArgs(BaseModel):
    patient_id: str = Field(description="The patient whose record to read.")


class PatientListArgs(BaseModel):
    patient_id: str = Field(description="The patient whose record to read.")
    limit: int | None = Field(
        default=None,
        gt=0,
        description="Maximum rows to return; the executor caps this to the scope's row cap.",
    )


class LabsArgs(BaseModel):
    patient_id: str = Field(description="The patient whose labs to read.")
    loinc_code: str | None = Field(
        default=None, description="Restrict to one analyte by exact LOINC code."
    )
    limit: int | None = Field(
        default=None,
        gt=0,
        description="Maximum results to return; the executor caps this to the scope's row cap.",
    )


class LabEducationArgs(BaseModel):
    loinc_code: str = Field(description="The LOINC code to resolve to a vetted education page.")


class MedicationEducationArgs(BaseModel):
    rxcui: str = Field(description="The RxNorm RxCUI to resolve to a vetted education page.")


class ReferenceRangeArgs(BaseModel):
    loinc_code: str = Field(description="The LOINC code whose curated reference band to read.")


# --- result items -----------------------------------------------------------


class PatientProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    given_name: str
    family_name: str
    birth_date: str
    gender: str
    language: str
    health_literacy_level: LiteracyLevel


class EncounterItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    encounter_id: str
    started_at: str
    stopped_at: str | None
    encounter_class: str
    code: str
    description: str
    reason_code: str | None
    reason_description: str | None


class LabItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str
    encounter_id: str
    taken_at: str
    loinc_code: str
    description: str
    value_number: float | None
    value_text: str | None
    units: str | None
    value_type: str


class MedicationItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    medication_id: str
    encounter_id: str
    started_on: str
    stopped_on: str | None
    rxcui: str
    description: str
    reason_description: str | None


class ConditionItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    encounter_id: str
    onset_on: str
    resolved_on: str | None
    code: str
    description: str


class ProcedureItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    procedure_id: str
    encounter_id: str
    performed_on: str
    code: str
    description: str
    reason_description: str | None


class AllergyItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    allergy_id: str
    recorded_on: str
    code: str
    description: str
    allergy_type: str | None
    category: str | None
    severity: str | None


class ClinicalNoteItem(BaseModel):
    """A note rendered from the structured record, never authored (§4.3).

    `fixture_kind` is carried through so the eval harness can find the planted
    injection fixture without string-matching note bodies.
    """

    model_config = ConfigDict(frozen=True)

    note_id: str
    encounter_id: str
    authored_at: str
    note_type: str
    body: str
    fixture_kind: str | None


class EducationPageItem(BaseModel):
    """One vetted, citable page. `url` and `attribution` are mandatory."""

    model_config = ConfigDict(frozen=True)

    code_system: str
    code: str
    title: str
    url: str
    summary_html: str
    attribution: str
    retrieved_at: str


class ReferenceBand(BaseModel):
    """A curated band with its citation *and its verbatim quote* (§3.7).

    A band with no citable published threshold is left null rather than
    invented, so the critical bounds are independently optional.
    """

    model_config = ConfigDict(frozen=True)

    loinc_code: str
    analyte: str
    specimen: str
    units: str
    reference_low: float | None
    reference_high: float | None
    reference_source_name: str
    reference_source_url: str
    reference_source_quote: str
    critical_low: float | None
    critical_high: float | None
    critical_source_name: str | None
    critical_source_url: str | None
    critical_source_quote: str | None
    population: str
    notes: str | None


# --- result envelopes -------------------------------------------------------


class PatientProfileResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    found: bool
    profile: PatientProfile | None


class EncountersResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    encounters: list[EncounterItem]
    count: int


class LabsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    labs: list[LabItem]
    count: int


class MedicationsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    medications: list[MedicationItem]
    count: int


class ConditionsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    conditions: list[ConditionItem]
    count: int


class ProceduresResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    procedures: list[ProcedureItem]
    count: int


class AllergiesResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    allergies: list[AllergyItem]
    count: int


class ClinicalNotesResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    notes: list[ClinicalNoteItem]
    count: int


class EducationResult(BaseModel):
    """Vetted pages for a code, or a declared gap (§4.2, case 14).

    `gap_declared` is true exactly when `pages` is empty: the assistant says it
    has no vetted education for the item and routes, rather than substituting a
    similar one.
    """

    model_config = ConfigDict(frozen=True)

    code_system: str
    code: str
    pages: list[EducationPageItem]
    gap_declared: bool


class ReferenceRangeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    loinc_code: str
    found: bool
    band: ReferenceBand | None
