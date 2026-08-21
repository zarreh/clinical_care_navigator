"""The only file that wires nodes and edges (docs/PLAN.md §9.3).

Phase 0 wires the walking skeleton. The real graph (docs/PLAN.md §5.1) replaces
`build_skeleton_graph` from Phase 3 onward; the node filename stays equal to the
registered node name so it also equals the trace span name.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from navigator.graph.nodes.done import done
from navigator.graph.nodes.echo import echo
from navigator.graph.state import SkeletonState

SkeletonGraph = CompiledStateGraph[SkeletonState, None, SkeletonState, SkeletonState]


def build_skeleton_graph() -> SkeletonGraph:
    workflow = StateGraph(SkeletonState)
    workflow.add_node("echo", echo)
    workflow.add_node("done", done)
    workflow.set_entry_point("echo")
    workflow.add_edge("echo", "done")
    workflow.add_edge("done", END)
    return workflow.compile()
