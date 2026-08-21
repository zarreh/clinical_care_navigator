"""Policy store behaviour — a table the clinical owner can edit, with a version."""

from __future__ import annotations

import re

from navigator.store import PolicyStore

ESCALATING = {"direct_to_emergency_care", "crisis"}


def test_rules_are_returned_in_severity_precedence_order(policy_store: PolicyStore) -> None:
    """Precedence is fixed, not emergent (§5.2)."""
    severities = [rule.severity for rule in policy_store.enabled_rules()]
    assert severities == sorted(severities, reverse=True)


def test_every_escalation_rule_carries_its_citation_into_the_store(
    policy_store: PolicyStore,
) -> None:
    for rule in policy_store.enabled_rules():
        if rule.action in ESCALATING:
            assert rule.source_url, rule.rule_id
            assert rule.source_quote, rule.rule_id


def test_every_pattern_compiles(policy_store: PolicyStore) -> None:
    """A rule that cannot compile is a rule that silently never fires."""
    for rule in policy_store.enabled_rules():
        re.compile(rule.pattern, re.IGNORECASE)


def test_the_table_is_versioned(policy_store: PolicyStore) -> None:
    assert policy_store.table_version() >= 1
