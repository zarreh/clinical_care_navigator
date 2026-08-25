"""Retrieve a patient's header for personalisation (reading level, name).

Patient-scoped: the executor forces `patient_id` to the session patient before
this runs, so the argument in the schema exists to inform the model, not to be
trusted (docs/PLAN.md §3.4).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import PatientIdArgs, PatientProfile, PatientProfileResult
from navigator.store import RecordStore

NAME = "get_patient_profile"


def build_get_patient_profile_tool(record_store: RecordStore) -> StructuredTool:
    def get_patient_profile(patient_id: str) -> PatientProfileResult:
        """Retrieve the patient's basic profile, including preferred language and
        health-literacy level, for tailoring the reading level of an answer.

        Args:
            patient_id: The patient whose profile to read.

        Returns:
            The profile, or ``found=False`` when the patient is unknown.
        """
        patient = record_store.get_patient(patient_id)
        if patient is None:
            return PatientProfileResult(patient_id=patient_id, found=False, profile=None)
        return PatientProfileResult(
            patient_id=patient_id,
            found=True,
            profile=PatientProfile(
                patient_id=patient.patient_id,
                given_name=patient.given_name,
                family_name=patient.family_name,
                birth_date=patient.birth_date,
                gender=patient.gender,
                language=patient.language,
                health_literacy_level=patient.health_literacy_level,
            ),
        )

    return StructuredTool.from_function(
        func=get_patient_profile, name=NAME, args_schema=PatientIdArgs
    )
