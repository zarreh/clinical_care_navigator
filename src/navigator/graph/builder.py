"""The only file that wires nodes and edges (docs/PLAN.md §9.3).

`build_skeleton_graph` is the Phase 0 walking skeleton, kept so the streaming
path stays proven. `build_navigator_graph` wires the real graph (§5.1): intake
loads the patient header; the pre-flight gate (screen_rules ∥ classify_intent →
resolve_policy) routes to a templated branch or into the investigate loop; the
investigate loop drives the scoped executor; draft_answer produces the cited
PatientAnswer; post-flight (extract_claims -> post_flight) runs the three
safety checks and routes to publish, a templated escalation, the review
queue, or back into the loop for a missing citation (§5.3).

Node filename == registered node name == trace span name (§9.3 rule 3).
"""

from pathlib import Path

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from navigator.graph.agents.explainer import Explainer, build_explainer
from navigator.graph.chains.answer_writer import AnswerWriterChain, build_answer_writer_chain
from navigator.graph.chains.claim_extractor import build_claim_extractor_chain
from navigator.graph.chains.intent_classifier import build_intent_classifier_chain
from navigator.graph.chains.scope_judge import build_scope_judge_chain
from navigator.graph.edges import (
    route_after_investigate,
    route_after_post_flight,
    route_after_resolve_policy,
)
from navigator.graph.nodes.budget_exceeded import budget_exceeded_node
from navigator.graph.nodes.classify_intent import build_classify_intent_node
from navigator.graph.nodes.done import done
from navigator.graph.nodes.draft_answer import build_draft_answer_node
from navigator.graph.nodes.echo import echo
from navigator.graph.nodes.enqueue_review import build_enqueue_review_node
from navigator.graph.nodes.extract_claims import build_extract_claims_node
from navigator.graph.nodes.intake import build_intake_node
from navigator.graph.nodes.investigate import build_investigate_node
from navigator.graph.nodes.post_flight import build_post_flight_node
from navigator.graph.nodes.publish import build_publish_node
from navigator.graph.nodes.resolve_policy_node import build_resolve_policy_node
from navigator.graph.nodes.screen_rules import build_screen_rules_node
from navigator.graph.nodes.template_response import build_template_response_node
from navigator.graph.policies import build_fast_model, build_reasoning_model
from navigator.graph.protocols import (
    ClaimExtractorChain,
    IntentClassifierChain,
    ScopeJudgeChain,
)
from navigator.graph.state import NavigatorState, SkeletonState
from navigator.guardrails.rule_engine import RuleEngine
from navigator.prompts.loader import load_prompt
from navigator.settings import Settings
from navigator.store import DEFAULT_ROW_CAP, EducationStore, PolicyStore, RecordStore
from navigator.tools import ScopedToolExecutor, build_registry

SkeletonGraph = CompiledStateGraph[SkeletonState, None, SkeletonState, SkeletonState]
NavigatorGraph = CompiledStateGraph[NavigatorState, None, NavigatorState, NavigatorState]


def build_skeleton_graph() -> SkeletonGraph:
    """Phase 0 walking skeleton: echo -> done."""
    workflow = StateGraph(SkeletonState)
    workflow.add_node("echo", echo)
    workflow.add_node("done", done)
    workflow.set_entry_point("echo")
    workflow.add_edge("echo", "done")
    workflow.add_edge("done", END)
    return workflow.compile()


def build_navigator_graph(
    settings: Settings,
    *,
    intent_chain: IntentClassifierChain | None = None,
    answer_writer_chain: AnswerWriterChain | None = None,
    explainer: Explainer | None = None,
    claim_extractor_chain: ClaimExtractorChain | None = None,
    scope_judge_chain: ScopeJudgeChain | None = None,
    checkpointer: Checkpointer = None,
) -> NavigatorGraph:
    """The only function that wires the navigator graph's nodes and edges.

    The LLM-backed pieces are injectable so the graph can be assembled and tested
    offline with stubs; in production they are built from the configured models.
    """
    record_store = RecordStore(Path(settings.record_db_path))
    education_store = EducationStore(Path(settings.education_db_path))
    policy_store = PolicyStore(Path(settings.policy_db_path))
    registry = build_registry(record_store, education_store)
    executor = ScopedToolExecutor(registry)
    rule_engine = RuleEngine(policy_store.enabled_rules())

    if (
        intent_chain is None
        or answer_writer_chain is None
        or explainer is None
        or claim_extractor_chain is None
        or scope_judge_chain is None
    ):
        fast_model = build_fast_model(settings)
        reasoning_model = build_reasoning_model(settings)
        if intent_chain is None:
            intent_chain = build_intent_classifier_chain(fast_model)
        if answer_writer_chain is None:
            answer_writer_chain = build_answer_writer_chain(reasoning_model)
        if explainer is None:
            # The explainer is bound to the full registry; the scoped executor
            # enforces the per-run ToolScope on every call, so the model can
            # propose anything and only in-scope calls execute (§3.3, §3.4).
            explainer = build_explainer(fast_model, list(registry.tools.values()))
        if claim_extractor_chain is None:
            # Claim extraction is a mechanical decomposition -> fast model.
            claim_extractor_chain = build_claim_extractor_chain(fast_model)
        if scope_judge_chain is None:
            # The scope judge is the one graded call -> reasoning model.
            scope_judge_chain = build_scope_judge_chain(reasoning_model)

    workflow = StateGraph(NavigatorState)
    # mypy cannot resolve add_node's overloads against a factory-returned
    # Callable (vs. a plain top-level function) — confirmed upstream limitation,
    # not a real type error; each node is unit-tested directly in tests/graph/.
    workflow.add_node("intake", build_intake_node(record_store, settings))  # type: ignore[arg-type]
    workflow.add_node("screen_rules", build_screen_rules_node(rule_engine))  # type: ignore[arg-type]
    workflow.add_node("classify_intent", build_classify_intent_node(intent_chain))  # type: ignore[arg-type]
    workflow.add_node(
        "resolve_policy",
        build_resolve_policy_node(policy_store, registry, DEFAULT_ROW_CAP),  # type: ignore[arg-type]
    )
    workflow.add_node(
        "investigate",
        build_investigate_node(  # type: ignore[arg-type]
            explainer, executor, load_prompt("explainer_v1")
        ),
    )
    workflow.add_node("draft_answer", build_draft_answer_node(answer_writer_chain))  # type: ignore[arg-type]
    workflow.add_node(
        "extract_claims",
        build_extract_claims_node(claim_extractor_chain),  # type: ignore[arg-type]
    )
    workflow.add_node(
        "post_flight",
        build_post_flight_node(  # type: ignore[arg-type]
            record_store.reference_range,
            scope_judge_chain,
            floor=settings.citation_coverage_floor,
            max_evidence_passes=settings.max_evidence_passes,
        ),
    )
    workflow.add_node("publish", build_publish_node())  # type: ignore[arg-type]
    workflow.add_node("enqueue_review", build_enqueue_review_node())  # type: ignore[arg-type]
    workflow.add_node("template_response", build_template_response_node(policy_store))  # type: ignore[arg-type]
    workflow.add_node("budget_exceeded", budget_exceeded_node)

    workflow.set_entry_point("intake")
    # screen_rules and classify_intent run in parallel after intake (§5.1).
    workflow.add_edge("intake", "screen_rules")
    workflow.add_edge("intake", "classify_intent")
    workflow.add_edge("screen_rules", "resolve_policy")
    workflow.add_edge("classify_intent", "resolve_policy")
    workflow.add_conditional_edges(
        "resolve_policy",
        route_after_resolve_policy,
        {
            "emergency": "template_response",
            "crisis": "template_response",
            "out_of_scope": "template_response",
            "clinician_review": "template_response",
            "allow": "investigate",
        },
    )
    workflow.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "investigate": "investigate",
            "draft_answer": "draft_answer",
            "budget_exceeded": "budget_exceeded",
        },
    )
    # Post-flight: the draft is decomposed, then the three checks run and route.
    workflow.add_edge("draft_answer", "extract_claims")
    workflow.add_edge("extract_claims", "post_flight")
    workflow.add_conditional_edges(
        "post_flight",
        route_after_post_flight,
        {
            "publish": "publish",
            "escalate": "template_response",
            "review": "enqueue_review",
            "investigate": "investigate",
        },
    )
    workflow.add_edge("publish", END)
    workflow.add_edge("enqueue_review", END)
    workflow.add_edge("template_response", END)
    workflow.add_edge("budget_exceeded", END)
    return workflow.compile(checkpointer=checkpointer)
