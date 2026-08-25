"""Guardrails: the deterministic safety layers.

`rule_engine` is the deterministic pre-flight screen with negation/attribution
handling; `autonomy` is the band boundary that never moves escalation;
`templates` are the four non-`allow` response branches. The LLM-backed layers
live in `graph/chains/`; combining them lives in `graph/nodes/resolve_policy.py`.
"""

from navigator.guardrails.autonomy import action_for_band, effective_band
from navigator.guardrails.rule_engine import RuleEngine
from navigator.guardrails.templates import render_template

__all__ = ["RuleEngine", "action_for_band", "effective_band", "render_template"]
