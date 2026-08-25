"""Citation-coverage check — post-flight check 2 (docs/PLAN.md §5.3).

Every *clinical* claim in the draft must resolve to something the run actually
retrieved — a recorded tool call (`tool_call_id`) or a vetted education URL. A
clinical claim that resolves to nothing is an unsupported assertion, and an
assistant that answers a patient's question about their own record with an
unsupported clinical assertion is exactly what this project exists to prevent
(§6.1, the traceability criterion).

*Navigational* claims — "you can ask your care team", "this page explains…" — are
exempt, and the exemption is explicit on each analysis (`reason`), never silent.
Coverage is the supported fraction of the clinical claims; when it falls below
the configured floor the run loops back once with specific feedback (the A2
grounding-loop pattern) and, if still short, routes to clinician review rather
than publishing an uncited clinical answer.

This is pure code: it resolves refs against the recorded evidence, it does not
ask a model whether a claim is "grounded enough".
"""

from __future__ import annotations

from collections.abc import Iterable

from navigator.schemas.answer import Claim
from navigator.schemas.postflight import ClaimAnalysis
from navigator.schemas.scoping import EvidenceRecord

_PAGES_KEY = "pages"
_URL_KEY = "url"


def _education_urls(evidence: list[EvidenceRecord]) -> set[str]:
    """Collect every vetted page URL the run retrieved.

    Education results carry their pages under `pages`, each with a `url`. These
    are valid citation targets alongside the `tool_call_id`s: an education claim
    cites the published page it came from, not the tool call that fetched it.
    """
    urls: set[str] = set()
    for record in evidence:
        pages = record.result.get(_PAGES_KEY)
        if not isinstance(pages, list):
            continue
        for page in pages:
            if isinstance(page, dict):
                url = page.get(_URL_KEY)
                if isinstance(url, str) and url:
                    urls.add(url)
    return urls


def _resolve(refs: Iterable[str], valid: set[str]) -> str | None:
    """Return the first ref that resolves to recorded evidence, or None."""
    for ref in refs:
        if ref in valid:
            return ref
    return None


def analyse_citations(
    claims: list[Claim],
    evidence: list[EvidenceRecord],
    *,
    education_urls: Iterable[str] = (),
    floor: float,
) -> tuple[list[ClaimAnalysis], float, list[str]]:
    """Analyse each claim's citation support and compute coverage.

    Valid refs are every recorded `tool_call_id` plus every vetted education URL
    (both those collected from the evidence and any passed in explicitly). A
    clinical claim is supported iff at least one of its `evidence_refs` resolves;
    a navigational claim is supported by exemption. Coverage is the supported
    fraction of the *clinical* claims (1.0 when there are none).

    Returns the per-claim analyses, the coverage fraction, and the ids of the
    unsupported clinical claims (the loop's feedback targets).
    """
    valid: set[str] = {record.tool_call_id for record in evidence}
    valid |= _education_urls(evidence)
    valid |= {url for url in education_urls if url}

    analyses: list[ClaimAnalysis] = []
    clinical_total = 0
    clinical_supported = 0
    uncited: list[str] = []

    for claim in claims:
        if claim.kind == "navigational":
            analyses.append(
                ClaimAnalysis(
                    claim_id=claim.id,
                    supported=True,
                    evidence_ref=None,
                    reason="navigational claim — exempt from citation coverage",
                )
            )
            continue

        clinical_total += 1
        resolved = _resolve(claim.evidence_refs, valid)
        if resolved is not None:
            clinical_supported += 1
            analyses.append(
                ClaimAnalysis(
                    claim_id=claim.id,
                    supported=True,
                    evidence_ref=resolved,
                    reason=f"resolves to recorded evidence {resolved!r}",
                )
            )
        else:
            uncited.append(claim.id)
            analyses.append(
                ClaimAnalysis(
                    claim_id=claim.id,
                    supported=False,
                    evidence_ref=None,
                    reason="clinical claim with no evidence_ref resolving to recorded evidence",
                )
            )

    coverage = 1.0 if clinical_total == 0 else clinical_supported / clinical_total
    # `floor` is accepted so callers can pass the configured value alongside the
    # inputs; the loop/review decision compares coverage to it in the node.
    _ = floor
    return analyses, coverage, uncited


def citation_feedback(claims: list[Claim], uncited_claim_ids: list[str]) -> str:
    """Compose the loop's feedback message naming the uncited claims (§5.3).

    The feedback is specific — it quotes each unsupported claim's text and asks
    for a citation to recorded evidence — so the second pass is a targeted fix,
    not a blind retry (the A2 grounding-judge feedback pattern).
    """
    by_id = {claim.id: claim for claim in claims}
    lines = [
        "The draft has clinical claims with no citation to retrieved evidence. "
        "Revise so each names a tool_call_id or a vetted education URL it rests on, "
        "or remove the claim:",
    ]
    for claim_id in uncited_claim_ids:
        claim = by_id.get(claim_id)
        if claim is not None:
            lines.append(f"- ({claim_id}) {claim.text}")
    return "\n".join(lines)
