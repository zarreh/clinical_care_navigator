"""Builds the eleven tools and records how the executor must treat each.

One store connection each, injected once -- not reopened per call, unlike the
source notebook (docs/PLAN.md §3.2). The registry also carries the two facts the
executor needs but a bare tool list does not express:

- **which tools are patient-scoped**, so their `patient_id` is overwritten with
  the session patient and a `SecurityEvent` is raised on a mismatch (§3.4);
- **which tools accept a `limit`**, so the executor can clamp it to the scope's
  row cap without guessing (§5.5).

`ToolScope` presets are built *here* rather than at the call site because a
non-`allow` gate decision must hand the executor a scope from which patient
tools are unreachable, not merely a filtered list (§3.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import StructuredTool

from navigator.schemas.scoping import ToolScope
from navigator.store import DEFAULT_ROW_CAP, EducationStore, RecordStore
from navigator.tools.get_allergies import build_get_allergies_tool
from navigator.tools.get_clinical_notes import build_get_clinical_notes_tool
from navigator.tools.get_conditions import build_get_conditions_tool
from navigator.tools.get_lab_reference_range import build_get_lab_reference_range_tool
from navigator.tools.get_labs import build_get_labs_tool
from navigator.tools.get_medications import build_get_medications_tool
from navigator.tools.get_patient_profile import build_get_patient_profile_tool
from navigator.tools.get_procedures import build_get_procedures_tool
from navigator.tools.list_patient_encounters import build_list_patient_encounters_tool
from navigator.tools.lookup_lab_education import build_lookup_lab_education_tool
from navigator.tools.lookup_medication_education import build_lookup_medication_education_tool

# Tools that read one patient's record: the executor forces `patient_id` to the
# session patient before they run (docs/PLAN.md §3.4).
PATIENT_SCOPED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "get_patient_profile",
        "list_patient_encounters",
        "get_labs",
        "get_medications",
        "get_conditions",
        "get_procedures",
        "get_allergies",
        "get_clinical_notes",
    }
)

# Code-keyed education and reference tools: a LOINC/RxCUI carries no patient
# identity, so these are reachable under a restricted scope.
EDUCATION_TOOL_NAMES: frozenset[str] = frozenset(
    {"lookup_lab_education", "lookup_medication_education", "get_lab_reference_range"}
)

# Tools whose `limit` argument the executor clamps to the scope's row cap.
LIMIT_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "list_patient_encounters",
        "get_labs",
        "get_medications",
        "get_conditions",
        "get_procedures",
        "get_allergies",
        "get_clinical_notes",
    }
)


@dataclass(frozen=True)
class ToolRegistry:
    """The bound tools plus the metadata the executor scopes them by."""

    tools: dict[str, StructuredTool]
    patient_scoped_names: frozenset[str]
    education_names: frozenset[str]
    limit_names: frozenset[str]

    @property
    def all_tool_names(self) -> frozenset[str]:
        return frozenset(self.tools)

    def full_scope(self, row_cap: int = DEFAULT_ROW_CAP) -> ToolScope:
        """Every tool -- the scope for an `allow` decision."""
        return ToolScope(allowed_tool_names=self.all_tool_names, row_cap=row_cap)

    def education_only_scope(self, row_cap: int = DEFAULT_ROW_CAP) -> ToolScope:
        """Only the code-keyed education tools; **no patient tool is reachable**.

        This is the scope a non-`allow` gate decision hands the executor, so
        minimum-necessary is a property of control flow rather than a prompt
        (docs/PLAN.md §3.3).
        """
        return ToolScope(allowed_tool_names=self.education_names, row_cap=row_cap)


def build_registry(record_store: RecordStore, education_store: EducationStore) -> ToolRegistry:
    """Builds all eleven tools, bound to the given store instances."""
    tools = [
        build_get_patient_profile_tool(record_store),
        build_list_patient_encounters_tool(record_store),
        build_get_labs_tool(record_store),
        build_get_medications_tool(record_store),
        build_get_conditions_tool(record_store),
        build_get_procedures_tool(record_store),
        build_get_allergies_tool(record_store),
        build_get_clinical_notes_tool(record_store),
        build_lookup_lab_education_tool(education_store),
        build_lookup_medication_education_tool(education_store),
        build_get_lab_reference_range_tool(record_store),
    ]
    return ToolRegistry(
        tools={tool.name: tool for tool in tools},
        patient_scoped_names=PATIENT_SCOPED_TOOL_NAMES,
        education_names=EDUCATION_TOOL_NAMES,
        limit_names=LIMIT_TOOL_NAMES,
    )
