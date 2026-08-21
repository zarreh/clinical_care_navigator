import json
from collections.abc import AsyncIterator

from navigator.graph.builder import SkeletonGraph
from navigator.graph.state import SkeletonState


async def stream_graph_events(
    graph: SkeletonGraph, initial_state: SkeletonState
) -> AsyncIterator[str]:
    """Bridges a LangGraph run to Server-Sent Events, one event per node step.

    The node filter is `name == metadata["langgraph_node"]` rather than a
    presence check on `langgraph_node`: conditional-edge routing functions also
    emit `on_chain_end` with the *source* node in their metadata, under their
    own function name.
    """
    async for event in graph.astream_events(initial_state, version="v2"):
        if event["event"] != "on_chain_end":
            continue
        node = event.get("metadata", {}).get("langgraph_node")
        if not node or event.get("name") != node:
            continue
        yield json.dumps({"node": node, "output": event.get("data", {}).get("output")}, default=str)
    yield json.dumps({"node": "__end__", "output": None})
