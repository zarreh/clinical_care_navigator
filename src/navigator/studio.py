"""Entry point for LangGraph Studio (`make studio`, see langgraph.json).

Exposes the real navigator graph, built exactly as the API builds it, so what
Studio draws and steps through is the production topology. It is compiled
*without* a checkpointer: `langgraph dev` supplies its own persistence, which is
what lets the `enqueue_review` interrupt pause and resume inside Studio.

Studio runs the graph directly, not through the API, so nothing is written to
the run store or the review queue from here.
"""

from __future__ import annotations

from navigator.graph.builder import build_navigator_graph
from navigator.settings import get_settings

graph = build_navigator_graph(get_settings())
