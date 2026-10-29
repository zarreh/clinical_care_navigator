"""Per-node LLM cost accounting via a LangChain callback (docs/PLAN.md §5.5).

Implemented in `zarreh_agentkit.cost` (v0.3.0 carries the three fixes this app
needed before it could stop keeping its own copy: the node tag is read from the
start event, structured-output calls fall back to `usage_metadata`, and dated
model snapshots price as their family); re-exported here so
`navigator.graph.cost_tracking` imports keep working.
"""

from zarreh_agentkit.cost import CostTrackingHandler, estimate_cost_usd

__all__ = ["CostTrackingHandler", "estimate_cost_usd"]
