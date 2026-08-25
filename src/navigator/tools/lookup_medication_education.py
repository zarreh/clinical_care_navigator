"""Resolve an RxCUI to its vetted MedlinePlus drug page(s).

Exact code lookup after RxNav ingredient normalisation happened at build time
(docs/PLAN.md §4.2). An empty result is a declared coverage gap, handled by
honesty rather than a fallback corpus (§4.2, canonical case 14).

Not patient-scoped -- an RxCUI carries no patient identity.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import EducationPageItem, EducationResult, MedicationEducationArgs
from navigator.store import EducationStore

NAME = "lookup_medication_education"


def build_lookup_medication_education_tool(education_store: EducationStore) -> StructuredTool:
    def lookup_medication_education(rxcui: str) -> EducationResult:
        """Resolve an RxNorm RxCUI to vetted, citable drug-education page(s).

        Args:
            rxcui: The RxNorm RxCUI to resolve.

        Returns:
            The matching pages with their citation URLs, or a declared gap
            (``gap_declared=True``, empty ``pages``) when none is vetted.
        """
        pages = education_store.for_rxcui(rxcui)
        return EducationResult(
            code_system="rxcui",
            code=rxcui,
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
        func=lookup_medication_education, name=NAME, args_schema=MedicationEducationArgs
    )
