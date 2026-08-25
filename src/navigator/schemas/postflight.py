"""Post-flight schemas — the centrepiece's typed records (docs/PLAN.md §5.3, §5.4).

Post-flight runs three checks in cost order over the draft answer, the recorded
tool evidence, and the pre-flight decision:

- ``critical_value`` (pure code) produces ``CriticalFinding``s — a retrieved lab
  value in a published critical band, which forces escalation regardless of the
  question. The finding carries the range row's own citation so the reader sees
  the basis (case 4).
- ``citation_coverage`` (pure code) produces ``ClaimAnalysis``es over the
  ``extract_claims`` output: every *clinical* claim must resolve to a recorded
  ``tool_call_id`` or an education URL; *navigational* claims are exempt and the
  exemption is explicit.
- ``scope_judge`` (one model call) produces a ``ScopeJudgement``: four narrow,
  falsifiable booleans with a span each — never a broad "is this safe?".

``PostFlightResult`` is the combined outcome the routing edge reads. Its
``override_action`` is the more-restrictive of the pre-flight action and the
check's implied action, so restriction is monotonic through the graph: post-flight
can escalate a run pre-flight allowed, but it can never *relax* a pre-flight
restriction (asserted by test).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from navigator.schemas.answer import Claim
from navigator.schemas.preflight import PolicyAction

# Which check drove the post-flight decision, recorded so the override-trigger
# rate (§6.3 chart 4) can be measured per trigger rather than in aggregate.
PostFlightTrigger = Literal["none", "critical_value", "citation_coverage", "scope_judge"]

# What the run does next after post-flight.
PostFlightDisposition = Literal["publish", "escalate", "review", "loop"]

CriticalBand = Literal["critical_low", "critical_high"]


class ExtractedClaims(BaseModel):
    """The claim extractor's structured output.

    An independent decomposition of the draft body, so extraction cannot smuggle
    in facts the draft did not state (§5.4, same argument as A2's claim extractor).
    """

    claims: list[Claim] = Field(default_factory=list)


class ClaimAnalysis(BaseModel):
    """One claim's citation-coverage verdict (§5.3 check 2).

    ``supported`` is true when a clinical claim resolves to a recorded
    ``tool_call_id`` or an education URL; ``evidence_ref`` records which one. A
    navigational claim is supported by exemption, and ``reason`` says so — the
    exemption is explicit, never silent.
    """

    model_config = ConfigDict(frozen=True)

    claim_id: str
    supported: bool
    evidence_ref: str | None = None
    reason: str


class CriticalFinding(BaseModel):
    """A retrieved lab value in a published critical band (§5.3 check 1).

    The reason case 4 works: a benign question over a critical potassium is
    escalated by pure code, regardless of what the question was or what the draft
    said. The finding carries the range row's own citation and verbatim quote so
    the escalation shows its basis rather than asserting it.
    """

    model_config = ConfigDict(frozen=True)

    loinc_code: str
    analyte: str
    value: float
    unit: str
    band: CriticalBand
    threshold: float
    action: PolicyAction
    source_name: str | None = None
    source_url: str | None = None
    source_quote: str | None = None


class ScopeJudgement(BaseModel):
    """The scope judge's structured output (§5.3 check 3).

    Four narrow closed questions, not "is this safe?" — a broad safety judgement
    from a model is unmeasurable, four boolean-with-span questions are testable
    and each maps to a specific rule a clinical owner can point at. ``spans``
    keys are the four field names; each value is the verbatim fragment of the
    draft that carries the violation.
    """

    model_config = ConfigDict(frozen=True)

    diagnoses: bool = False
    changes_medication: bool = False
    directs_clinical_action: bool = False
    contradicts_record: bool = False
    spans: dict[str, str] = Field(default_factory=dict)

    @property
    def any_violation(self) -> bool:
        return (
            self.diagnoses
            or self.changes_medication
            or self.directs_clinical_action
            or self.contradicts_record
        )


class PostFlightResult(BaseModel):
    """The combined post-flight outcome the routing edge reads (§5.3).

    ``disposition`` is the next step; ``trigger`` is which check drove it
    (recorded for the override-trigger chart). ``override_action`` is the
    more-restrictive of the pre-flight action and the check's implied action —
    the monotonic guarantee. It is ``None`` on a clean publish, when nothing
    overrode.
    """

    model_config = ConfigDict(frozen=True)

    disposition: PostFlightDisposition
    trigger: PostFlightTrigger = "none"
    override_action: PolicyAction | None = None
    critical_findings: list[CriticalFinding] = Field(default_factory=list)
    claim_analyses: list[ClaimAnalysis] = Field(default_factory=list)
    citation_coverage: float = 1.0
    uncited_claim_ids: list[str] = Field(default_factory=list)
    scope_judgement: ScopeJudgement | None = None
    evidence_pass: int = 0
