"""The deterministic screen, with its negation/attribution check (§5.2 layer 1).

The credibility property is case 12: a red-flag phrase quoted from the record
must be seen, recorded, and *not* fired. Substring matching alone is not a
guardrail (§3.2, D-A3-2) — these tests pin the context check that makes it one.
"""

from __future__ import annotations

from navigator.guardrails.rule_engine import RuleEngine


def _firing_ids(engine: RuleEngine, question: str) -> set[str]:
    return {match.rule_id for match in engine.firing(question)}


def test_chest_pain_fires(rule_engine: RuleEngine) -> None:
    assert "rf-cardiac-chest-pain" in _firing_ids(
        rule_engine, "Crushing chest pain, my left arm is numb"
    )


def test_negated_red_flag_does_not_fire(rule_engine: RuleEngine) -> None:
    # "no chest pain" is a denial, not a symptom.
    assert "rf-cardiac-chest-pain" not in _firing_ids(rule_engine, "I have no chest pain")


def test_attributed_red_flag_does_not_fire(rule_engine: RuleEngine) -> None:
    # Canonical case 12: quoting the discharge note is not asserting a symptom.
    matches = rule_engine.screen("my discharge note says to watch for chest pain")
    chest = [m for m in matches if m.rule_id == "rf-cardiac-chest-pain"]
    assert chest, "the term should still be seen and recorded"
    assert all(m.attributed for m in chest)
    assert all(not m.fires for m in chest)


def test_suppressed_match_is_still_recorded(rule_engine: RuleEngine) -> None:
    # A suppressed match is evidence the layer saw the term and chose not to
    # fire — the auditable property.
    matches = rule_engine.screen("my discharge note says to watch for chest pain")
    assert any(m.rule_id == "rf-cardiac-chest-pain" for m in matches)


def test_metaphor_does_not_fire_deterministic_layer(rule_engine: RuleEngine) -> None:
    # Case 11 defeats the lexicon by design; the classifier layer must catch it.
    assert not rule_engine.firing("like an elephant sitting on my chest")


def test_dosing_fires(rule_engine: RuleEngine) -> None:
    assert "scope-dosing" in _firing_ids(rule_engine, "How much ibuprofen should I take?")


def test_medication_change_fires(rule_engine: RuleEngine) -> None:
    assert "scope-stop-or-change-medication" in _firing_ids(
        rule_engine, "Should I stop taking my metformin?"
    )


def test_out_of_domain_fires(rule_engine: RuleEngine) -> None:
    assert "scope-out-of-domain" in _firing_ids(rule_engine, "What's the weather?")


def test_self_harm_fires(rule_engine: RuleEngine) -> None:
    assert "rf-self-harm" in _firing_ids(rule_engine, "I want to kill myself")
