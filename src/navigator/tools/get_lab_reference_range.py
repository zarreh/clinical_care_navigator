"""Resolve a LOINC code to its curated reference band.

Every band carries its citation *and its verbatim published quote* (docs/PLAN.md
§3.7, §4.3), so an answer can show the reader the sentence a range came from
rather than asserting "normal" on the author's authority. A LOINC not in the
table returns ``found=False`` -- the assistant never estimates a band.

Not patient-scoped -- a reference band is population-level, not a patient value.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from navigator.schemas.tools import ReferenceBand, ReferenceRangeArgs, ReferenceRangeResult
from navigator.store import RecordStore

NAME = "get_lab_reference_range"


def build_get_lab_reference_range_tool(record_store: RecordStore) -> StructuredTool:
    def get_lab_reference_range(loinc_code: str) -> ReferenceRangeResult:
        """Resolve a LOINC code to its curated reference band, with the cited,
        verbatim published quote each bound came from.

        Args:
            loinc_code: The LOINC code whose reference band to read.

        Returns:
            The band, or ``found=False`` when the curated table does not cover
            the code. A missing band is never estimated.
        """
        band = record_store.reference_range(loinc_code)
        if band is None:
            return ReferenceRangeResult(loinc_code=loinc_code, found=False, band=None)
        return ReferenceRangeResult(
            loinc_code=loinc_code,
            found=True,
            band=ReferenceBand(
                loinc_code=band.loinc_code,
                analyte=band.analyte,
                specimen=band.specimen,
                units=band.units,
                reference_low=band.reference_low,
                reference_high=band.reference_high,
                reference_source_name=band.reference_source_name,
                reference_source_url=band.reference_source_url,
                reference_source_quote=band.reference_source_quote,
                critical_low=band.critical_low,
                critical_high=band.critical_high,
                critical_source_name=band.critical_source_name,
                critical_source_url=band.critical_source_url,
                critical_source_quote=band.critical_source_quote,
                population=band.population,
                notes=band.notes,
            ),
        )

    return StructuredTool.from_function(
        func=get_lab_reference_range, name=NAME, args_schema=ReferenceRangeArgs
    )
