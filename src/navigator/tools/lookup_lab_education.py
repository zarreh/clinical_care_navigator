"""Resolve a LOINC code to its vetted MedlinePlus education page(s).

Exact code lookup, not similarity search (docs/PLAN.md §5.6, D-A3-5). An empty
result is a *declared coverage gap*, not a failure: the assistant says it has no
vetted education for the test and routes, rather than substituting a similar one
or generating text (§4.2, canonical case 14).

Not patient-scoped -- a LOINC code carries no patient identity.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import EducationPageItem, EducationResult, LabEducationArgs
from navigator.store import EducationStore

NAME = "lookup_lab_education"


def build_lookup_lab_education_tool(education_store: EducationStore) -> StructuredTool:
    def lookup_lab_education(loinc_code: str) -> EducationResult:
        """Resolve a LOINC code to vetted, citable patient-education page(s).

        Args:
            loinc_code: The LOINC code to resolve.

        Returns:
            The matching pages with their citation URLs, or a declared gap
            (``gap_declared=True``, empty ``pages``) when none is vetted.
        """
        pages = education_store.for_loinc(loinc_code)
        return EducationResult(
            code_system="loinc",
            code=loinc_code,
            pages=[
                EducationPageItem(
                    code_system=p.code_system,
                    code=p.code,
                    title=p.title,
                    url=p.url,
                    summary_html=p.summary_html,
                    attribution=p.attribution,
                    retrieved_at=p.retrieved_at,
                )
                for p in pages
            ],
            gap_declared=not pages,
        )

    return StructuredTool.from_function(
        func=lookup_lab_education, name=NAME, args_schema=LabEducationArgs
    )
