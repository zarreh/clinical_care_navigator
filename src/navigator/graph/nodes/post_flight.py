"""Post-flight — the centrepiece (docs/PLAN.md §5.3).

Three checks run over the finished draft, in cost order, each able to *escalate*
the run but never to relax the pre-flight decision:

1. **critical_value** (pure code, cheapest): a retrieved lab value in a published
   panic band forces the emergency route regardless of the question — canonical
   case 4. This runs first because it is free and the most serious.
2. **citation_coverage** (pure code): every clinical claim must resolve to
   recorded evidence. Below the floor the run loops back once with specific
   feedback (bumping `evidence_pass`); if a second pass still falls short it
   routes to clinician review rather than publishing an uncited clinical answer.
3. **scope_judge** (one model call, most expensive, runs last): four narrow
   boundary questions. Diagnosing or changing a medication is out of scope and
   escalates; directing a clinical action or contradicting the record is held
   for clinician review.

The override action is always `more_restrictive(pre_flight_action, implied)`, so
restriction is monotonic: post-flight can raise the bar but the pre-flight
decision is a floor it can never lower (asserted directly by test).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage

from navigator.graph.protocols import ScopeJudgeChain
from navigator.graph.state import NavigatorState
from navigator.guardrails.citation_check import analyse_citations, citation_feedback
from navigator.guardrails.critical_values import (
    CRITICAL_VALUE_ACTION,
    ReferenceRangeLookup,
    scan_critical_values,
)
from navigator.schemas.postflight import PostFlightResult
from navigator.schemas.preflight import more_restrictive


def build_post_flight_node(
    reference_range: ReferenceRangeLookup,
    scope_judge_chain: ScopeJudgeChain,
    *,
    floor: float,
    max_evidence_passes: int,
) -> Callable[[NavigatorState], dict[str, object]]:
    def post_flight_node(state: NavigatorState) -> dict[str, object]:
        draft = state["draft"]
        evidence = state.get("evidence", [])
        claims = state.get("claims", [])
        pre_action = state["policy_decision"].action
        evidence_pass = state.get("evidence_pass", 0)

        # --- check 1: critical values (pure code, cheapest, most serious) ---
        findings = scan_critical_values(evidence, reference_range)
        if findings:
            return {
                "post_flight": PostFlightResult(
                    disposition="escalate",
                    trigger="critical_value",
                    override_action=more_restrictive(pre_action, CRITICAL_VALUE_ACTION),
                    critical_findings=findings,
                    evidence_pass=evidence_pass,
                )
            }

        # --- check 2: citation coverage (pure code) ---
        analyses, coverage, uncited = analyse_citations(claims, evidence, floor=floor)
        if coverage < floor:
            if evidence_pass < max_evidence_passes:
                # Loop back once with specific feedback naming the uncited claims.
                feedback = citation_feedback(claims, uncited)
                return {
                    "post_flight": PostFlightResult(
                        disposition="loop",
                        trigger="citation_coverage",
                        claim_analyses=analyses,
                        citation_coverage=coverage,
                        uncited_claim_ids=uncited,
                        evidence_pass=evidence_pass + 1,
                    ),
                    "evidence_pass": evidence_pass + 1,
                    "messages": [*state.get("messages", []), HumanMessage(content=feedback)],
                }
            # Still short after the retry: hold for review, do not publish uncited.
            return {
                "post_flight": PostFlightResult(
                    disposition="review",
                    trigger="citation_coverage",
                    override_action=more_restrictive(pre_action, "clinician_review"),
                    claim_analyses=analyses,
                    citation_coverage=coverage,
                    uncited_claim_ids=uncited,
                    evidence_pass=evidence_pass,
                )
            }

        # --- check 3: scope judge (one model call, most expensive, runs last) ---
        judgement = scope_judge_chain.invoke({"draft_body": draft.body})
        if judgement.diagnoses or judgement.changes_medication:
            return {
                "post_flight": PostFlightResult(
                    disposition="escalate",
                    trigger="scope_judge",
                    override_action=more_restrictive(pre_action, "out_of_scope"),
                    claim_analyses=analyses,
                    citation_coverage=coverage,
                    scope_judgement=judgement,
                    evidence_pass=evidence_pass,
                )
            }
        if judgement.directs_clinical_action or judgement.contradicts_record:
            return {
                "post_flight": PostFlightResult(
                    disposition="review",
                    trigger="scope_judge",
                    override_action=more_restrictive(pre_action, "clinician_review"),
                    claim_analyses=analyses,
                    citation_coverage=coverage,
                    scope_judgement=judgement,
                    evidence_pass=evidence_pass,
                )
            }

        # --- all three checks clear: publish ---
        return {
            "post_flight": PostFlightResult(
                disposition="publish",
                trigger="none",
                claim_analyses=analyses,
                citation_coverage=coverage,
                scope_judgement=judgement,
                evidence_pass=evidence_pass,
            )
        }

    return post_flight_node
