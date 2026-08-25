"""Typed row models for the record, education and policy stores.

Plain frozen dataclasses, not Pydantic: these are internal read models, not
API or tool boundaries. Tool returns are Pydantic and live in `schemas/`
(docs/PLAN.md §3.6).
"""

from __future__ import annotations

from dataclasses import dataclass

from navigator.schemas.common import LiteracyLevel


@dataclass(frozen=True)
class Patient:
    """A synthetic patient header.

    `language` and `health_literacy_level` have no Synthea equivalent and are
    assigned deterministically by `data/build_store.py`. The docs say so
    plainly rather than implying Synthea produced them (docs/PLAN.md §4.3).
    """

    patient_id: str
    given_name: str
    family_name: str
    birth_date: str
    gender: str
    language: str
    health_literacy_level: LiteracyLevel


@dataclass(frozen=True)
class Encounter:
    encounter_id: str
    patient_id: str
    started_at: str
    stopped_at: str | None
    encounter_class: str
    code: str
    description: str
    reason_code: str | None
    reason_description: str | None


@dataclass(frozen=True)
class Observation:
    """One recorded measurement.

    `loinc_code` is carried through from Synthea rather than looked up — it is
    what makes an exact MedlinePlus Connect citation possible without ever
    downloading the LOINC table (docs/PLAN.md §4.2, D-A3-5).
    """

    observation_id: str
    patient_id: str
    encounter_id: str
    taken_at: str
    category: str
    loinc_code: str
    description: str
    value_number: float | None
    value_text: str | None
    units: str | None
    value_type: str


@dataclass(frozen=True)
class Medication:
    medication_id: str
    patient_id: str
    encounter_id: str
    started_on: str
    stopped_on: str | None
    rxcui: str
    description: str
    reason_description: str | None


@dataclass(frozen=True)
class Condition:
    condition_id: str
    patient_id: str
    encounter_id: str
    onset_on: str
    resolved_on: str | None
    code: str
    description: str


@dataclass(frozen=True)
class Procedure:
    procedure_id: str
    patient_id: str
    encounter_id: str
    performed_on: str
    code: str
    description: str
    reason_description: str | None


@dataclass(frozen=True)
class Allergy:
    allergy_id: str
    patient_id: str
    recorded_on: str
    code: str
    description: str
    allergy_type: str | None
    category: str | None
    severity: str | None


@dataclass(frozen=True)
class ClinicalNote:
    """A note **rendered** from the structured record, never authored.

    `fixture_kind` marks a note carrying a deliberately planted adversarial
    payload — canonical case 7's indirect prompt injection (docs/PLAN.md §4.5).
    Marking it in the row is what lets a test assert the fixture is present and
    lets the eval harness find it without string-matching note bodies.
    """

    note_id: str
    patient_id: str
    encounter_id: str
    authored_at: str
    note_type: str
    body: str
    fixture_kind: str | None


@dataclass(frozen=True)
class ReferenceRange:
    """One analyte's bands, from `data/lab_reference_ranges.csv`.

    Three bands, not two: a reference band plus a **critical** band. The
    critical band is what makes post-flight escalation on a benign question
    possible at all — canonical case 4 (docs/PLAN.md §5.3).

    Each band carries its own citation *and its own verbatim quote*. Quoting
    rather than interpreting is the §3.7 vocabulary rule applied to the data
    layer, and it is what lets the answer show a reader the published sentence
    a band came from. A band with no citable published threshold is left empty
    rather than invented, so `critical_low` and `critical_high` are independently
    optional.
    """

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

    @property
    def has_critical_band(self) -> bool:
        return self.critical_low is not None or self.critical_high is not None


@dataclass(frozen=True)
class EducationPage:
    """One vetted, citable education page as returned by MedlinePlus Connect.

    Only what the service returned is stored — title, URL, summary, attribution
    — with `retrieved_at` for the TTL. NLM permits linking to and displaying
    returned data; it does not permit copying MedlinePlus pages (NOTICE.md).
    """

    code_system: str
    code: str
    title: str
    url: str
    summary_html: str
    attribution: str
    retrieved_at: str


@dataclass(frozen=True)
class CoverageGap:
    """A code with no vetted education page.

    Recorded rather than filled. The assistant declares the gap instead of
    substituting a similar test or generating text (docs/PLAN.md §4.2).
    """

    code_system: str
    code: str
    label: str
    checked_at: str


@dataclass(frozen=True)
class PolicyRule:
    """One row of the editable safety rule table.

    `source_url` and `source_quote` are mandatory for every escalation rule: no
    rule that sends a patient to emergency care rests on the author's own
    clinical judgement (docs/PLAN.md §4.4). Scope rules — dosing, medication
    change — carry none, because they are boundaries this project set rather
    than clinical findings, and that difference is worth keeping visible.
    """

    rule_id: str
    action: str
    band: str
    category: str
    pattern: str
    description: str
    template_id: str
    severity: int
    source_name: str | None
    source_url: str | None
    source_quote: str | None
    version: int
    enabled: bool


# --- Operational records (docs/PLAN.md §7 Phase 6) --------------------------
#
# Unlike the read models above, these describe *operational* state written at
# run time by the RunStore, ReviewQueue and the cost-accounting callback — not
# build-time clinical data. They are frozen dataclasses for the same reason:
# small internal records that never leave the process as a public contract.


@dataclass(frozen=True)
class CostEntry:
    """One attributed LLM call within a graph run (docs/PLAN.md §5.5).

    The node is resolved from LangGraph's ``langgraph_node`` run metadata, so a
    single callback attached to the whole invocation attributes every call back
    to the node that made it — no plumbing through node code.
    """

    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class RunRecord:
    """The operational record of one conversation run.

    ``status`` is one of ``running``, ``answered``, ``pending_review``,
    ``templated`` or ``failed``. ``answer_kind``/``answer_json`` carry the final
    ``PatientAnswer`` once the run reaches a terminal state; a run held for a
    clinician is ``pending_review`` with the drafted (not yet published) body.
    """

    id: str
    question: str
    patient_id: str
    status: str
    created_at: str
    updated_at: str
    answer_kind: str | None
    answer_json: str | None
    error: str | None


@dataclass(frozen=True)
class RunEvent:
    """One node boundary persisted during a run, so the stream replays whether a
    client watches live or reconnects long after the run finished."""

    run_id: str
    sequence: int
    node: str
    payload_json: str
    created_at: str


@dataclass(frozen=True)
class ReviewItem:
    """One draft held for a clinician (docs/PLAN.md §5.10).

    ``thread_id`` is the LangGraph checkpoint thread the run suspended on, so a
    reviewer decision resumes the *same* interrupted run from its checkpoint
    rather than starting a new one. ``status`` is ``pending`` until a decision
    resolves it to ``approved``, ``edited`` or ``declined``.
    """

    id: str
    run_id: str
    thread_id: str
    patient_id: str
    reason: str
    override_action: str | None
    body: str
    payload_json: str
    status: str
    created_at: str
    updated_at: str
