"""Post-flight check 2: citation coverage (§5.3)."""

from __future__ import annotations

from navigator.guardrails.citation_check import analyse_citations, citation_feedback
from navigator.schemas.answer import Claim
from navigator.schemas.scoping import EvidenceRecord

_EDU_URL = "https://medlineplus.gov/ency/article/003484.htm"


def _labs_evidence(call_id: str = "call-1") -> EvidenceRecord:
    return EvidenceRecord(
        tool_call_id=call_id,
        tool_name="get_labs",
        args_after_scoping={},
        result={"labs": [{"loinc_code": "2823-3", "value_number": 6.9}]},
        retrieved_at="2026-08-20T00:00:00+00:00",
    )


def _education_evidence(call_id: str = "call-2") -> EvidenceRecord:
    return EvidenceRecord(
        tool_call_id=call_id,
        tool_name="lookup_lab_education",
        args_after_scoping={},
        result={"pages": [{"url": _EDU_URL}], "gap_declared": False},
        retrieved_at="2026-08-20T00:00:00+00:00",
    )


def test_clinical_claim_supported_by_tool_call() -> None:
    claims = [
        Claim(id="c1", text="Your potassium is high.", kind="clinical", evidence_refs=["call-1"])
    ]
    analyses, coverage, uncited = analyse_citations(claims, [_labs_evidence()], floor=1.0)
    assert coverage == 1.0
    assert uncited == []
    assert analyses[0].supported is True
    assert analyses[0].evidence_ref == "call-1"


def test_clinical_claim_supported_by_education_url() -> None:
    claims = [
        Claim(
            id="c1",
            text="High potassium affects the heart.",
            kind="clinical",
            evidence_refs=[_EDU_URL],
        )
    ]
    analyses, coverage, uncited = analyse_citations(claims, [_education_evidence()], floor=1.0)
    assert coverage == 1.0
    assert analyses[0].evidence_ref == _EDU_URL


def test_navigational_claim_is_exempt() -> None:
    claims = [Claim(id="c1", text="Message your care team.", kind="navigational", evidence_refs=[])]
    analyses, coverage, uncited = analyse_citations(claims, [], floor=1.0)
    # No clinical claims -> coverage is 1.0, and the exemption is explicit.
    assert coverage == 1.0
    assert uncited == []
    assert analyses[0].supported is True
    assert "navigational" in analyses[0].reason


def test_uncited_clinical_claim_lowers_coverage() -> None:
    claims = [
        Claim(id="c1", text="Your potassium is high.", kind="clinical", evidence_refs=["call-1"]),
        Claim(
            id="c2", text="You should take 40mg of X.", kind="clinical", evidence_refs=["call-999"]
        ),
    ]
    analyses, coverage, uncited = analyse_citations(claims, [_labs_evidence()], floor=1.0)
    assert coverage == 0.5
    assert uncited == ["c2"]
    assert {a.claim_id: a.supported for a in analyses} == {"c1": True, "c2": False}


def test_feedback_names_the_uncited_claims() -> None:
    claims = [Claim(id="c2", text="You should take 40mg of X.", kind="clinical", evidence_refs=[])]
    message = citation_feedback(claims, ["c2"])
    assert "c2" in message
    assert "40mg of X" in message
