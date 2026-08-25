"""The pre-flight gate's combining node (§5.2) against the canonical cases.

These tests run with no LLM and no network: the intent classifier is a stub
returning a fixed `IntentAssessment`, and the rule engine runs against the
offline fixture policy table. The exit criteria pinned here:

- canonical cases 2, 3, 9, 10, 11, 12, 13 route to the expected action;
- a non-`allow` decision binds a scope from which every patient tool is absent
  (refusal short-circuits before PHI, §3.3);
- layer disagreement is recorded, not smoothed over;
- the same question produces different bands at L1/L2/L3 but identical
  escalation at all three (§5.9).
"""

from __future__ import annotations

import pytest

from navigator.graph.nodes.resolve_policy import resolve_policy
from navigator.guardrails.rule_engine import RuleEngine
from navigator.schemas.preflight import IntentAssessment, PolicyDecision, RedFlag
from navigator.settings import AutonomyLevel
from navigator.store.models import PolicyRule
from navigator.tools import ToolRegistry

ROW_CAP = 25


def _assess(
    question_class: str,
    flags: tuple[tuple[str, str], ...] = (),
    span: str = "",
) -> IntentAssessment:
    return IntentAssessment(
        question_class=question_class,  # type: ignore[arg-type]
        red_flags=[RedFlag(category=c, span=s) for c, s in flags],
        confidence=0.9,
        rationale_span=span,
    )


def _decide(
    question: str,
    assessment: IntentAssessment,
    rule_engine: RuleEngine,
    policy_rules: list[PolicyRule],
    registry: ToolRegistry,
    autonomy_level: AutonomyLevel = "L2_balanced",
) -> PolicyDecision:
    return resolve_policy(
        question,
        firing=rule_engine.firing(question),
        all_matches=rule_engine.screen(question),
        assessment=assessment,
        rules=policy_rules,
        registry=registry,
        autonomy_level=autonomy_level,
        row_cap=ROW_CAP,
    )


# --- canonical cases --------------------------------------------------------


def test_case2_medication_stop_is_out_of_scope(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "Should I stop taking my metformin?",
        _assess("decision_adjacent", span="stop taking"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "out_of_scope"
    assert decision.template_id == "out_of_scope_medication_change"


def test_case3_chest_pain_directs_to_emergency(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "Crushing chest pain, my left arm is numb",
        _assess("red_flag", (("cardiac", "chest pain"),), "chest pain"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "direct_to_emergency_care"
    assert decision.template_id == "emergency_cardiac"


def test_case9_dosing_is_out_of_scope(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "How much ibuprofen should I take?",
        _assess("decision_adjacent", span="How much"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "out_of_scope"
    assert decision.template_id == "out_of_scope_dosing"


def test_case10_weather_is_out_of_scope(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "What's the weather?",
        _assess("out_of_scope", span="weather"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "out_of_scope"


def test_case11_metaphor_emergency_via_classifier(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    # The deterministic screen fires nothing; the classifier catches the
    # metaphor. The more restrictive (classifier) action must win.
    question = "like an elephant sitting on my chest"
    assert not rule_engine.firing(question)  # the lexicon is defeated
    decision = _decide(
        question,
        _assess("red_flag", (("cardiac", "elephant sitting on my chest"),), "elephant"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "direct_to_emergency_care"


def test_case12_attributed_red_flag_is_ordinary_answer(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "my discharge note says to watch for chest pain",
        _assess("record_lookup", span="discharge note"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "allow"


def test_case13_self_harm_is_crisis_not_emergency(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "I want to kill myself",
        _assess("red_flag", (("self_harm", "kill myself"),), "kill myself"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "crisis"
    assert decision.template_id == "crisis_988"


# --- exit criteria ----------------------------------------------------------


@pytest.mark.parametrize(
    "question,assessment",
    [
        ("Should I stop taking my metformin?", _assess("decision_adjacent", span="stop")),
        ("Crushing chest pain", _assess("red_flag", (("cardiac", "chest pain"),), "chest pain")),
        ("What's the weather?", _assess("out_of_scope", span="weather")),
        ("I want to kill myself", _assess("red_flag", (("self_harm", "kill myself"),), "kill")),
    ],
)
def test_non_allow_decisions_bind_scope_with_no_patient_tools(
    question: str,
    assessment: IntentAssessment,
    rule_engine: RuleEngine,
    policy_rules: list[PolicyRule],
    registry: ToolRegistry,
) -> None:
    decision = _decide(question, assessment, rule_engine, policy_rules, registry)
    assert decision.action != "allow"
    # Refusal short-circuits before PHI: no patient tool is reachable (§3.3).
    assert not (decision.tool_scope.allowed_tool_names & registry.patient_scoped_names)


def test_allow_decision_binds_full_scope(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "What does my A1c of 7.8 mean?",
        _assess("lab_education", span="A1c"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "allow"
    assert registry.patient_scoped_names <= decision.tool_scope.allowed_tool_names


def test_layer_disagreement_is_recorded(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    # Screen fires out_of_scope (dosing); classifier thinks it is a benign
    # medication-education question. The more restrictive wins and the
    # disagreement is recorded.
    decision = _decide(
        "How much ibuprofen should I take?",
        _assess("medication_education", span="ibuprofen"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.action == "out_of_scope"  # more restrictive wins
    assert decision.layer_agreement is False


def test_layer_agreement_recorded_when_layers_agree(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    decision = _decide(
        "Crushing chest pain",
        _assess("red_flag", (("cardiac", "chest pain"),), "chest pain"),
        rule_engine,
        policy_rules,
        registry,
    )
    assert decision.layer_agreement is True


def test_same_question_different_bands_across_autonomy_levels(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    question = "What does my A1c of 7.8 mean?"
    assessment = _assess("lab_education", span="A1c")
    bands = {
        level: _decide(question, assessment, rule_engine, policy_rules, registry, level).band
        for level in ("L1_conservative", "L2_balanced", "L3_permissive")
    }
    # L1 moves the boundary down (inform -> recommend); L2/L3 leave it inform.
    assert bands["L1_conservative"] == "recommend"
    assert bands["L2_balanced"] == "inform"
    assert bands["L3_permissive"] == "inform"


def test_identical_escalation_across_autonomy_levels(
    rule_engine: RuleEngine, policy_rules: list[PolicyRule], registry: ToolRegistry
) -> None:
    question = "Crushing chest pain"
    assessment = _assess("red_flag", (("cardiac", "chest pain"),), "chest pain")
    actions = {
        level: _decide(question, assessment, rule_engine, policy_rules, registry, level).action
        for level in ("L1_conservative", "L2_balanced", "L3_permissive")
    }
    # The escalate boundary never moves (§5.9).
    assert set(actions.values()) == {"direct_to_emergency_care"}
