"""The answer schemas (docs/PLAN.md §5.4).

`PatientAnswer` is the frozen, final answer object — assembled deterministically
by `publish` from the already-judged draft plus the policy record, and never
altered by a model after post-flight passes (§5.1 property 5, D-A3-6).

`Claim` is one assertion in the answer, classified as *clinical* (must carry a
resolvable citation) or *navigational* (exempt, and the exemption is explicit —
§5.3). `Citation` is a resolvable reference: either a recorded `tool_call_id`
from the run's evidence or an education-source URL. Citation coverage is not a
quality metric here — it is the design constraint that keeps the app outside the
FDA's Clinical Decision Support device definition (§6.1, §3.5).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimKind = Literal["clinical", "navigational"]


class Claim(BaseModel):
    """One assertion in the answer, with the evidence it rests on.

    `evidence_refs` are `tool_call_id`s from the run's `EvidenceRecord`s or
    education-source URLs. A clinical claim with no resolvable ref fails
    citation coverage in post-flight (§5.3).
    """

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    kind: ClaimKind
    evidence_refs: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    """A resolvable citation surfaced to the reader.

    `source` is the recorded tool call or the education page; `url` is present
    for education sources so the reader can independently review the basis of
    the output — one of the four FDA CDS device-exclusion criteria (§6.1).
    """

    model_config = ConfigDict(frozen=True)

    claim_id: str
    tool_call_id: str | None = None
    url: str | None = None
    title: str | None = None


class PatientAnswer(BaseModel):
    """The final answer, frozen once post-flight passes.

    `reading_level_target` comes from the patient's literacy level and is shown
    in the UI — adapting to a person *with* them, not silently (§3.7).
    `reading_level_measured` is computed over `body` so the equity claim is
    measured, not asserted (§8).
    """

    model_config = ConfigDict(frozen=True)

    body: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    reading_level_target: float
    reading_level_measured: float | None = None
    autonomy_level: str
    disposition: Literal["answered", "pending_review", "templated"] = "answered"
    pending_review: bool = False
