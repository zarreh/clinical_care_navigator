import asyncio
import json
from collections.abc import AsyncIterator

from navigator.graph.builder import SkeletonGraph
from navigator.graph.state import SkeletonState
from navigator.store.run_store import RunStore

_POLL_INTERVAL_SECONDS = 0.25


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


async def stream_conversation_events(run_store: RunStore, run_id: str) -> AsyncIterator[str]:
    """Replays every event already persisted for a conversation, then — while the
    run is still executing — tails newly-appended events until it reaches a
    terminal status. Works identically whether the patient connects the instant a
    run starts or reconnects long after it finished (docs/PLAN.md §5.8).

    These events are the patient's own record and are deliberately not redacted;
    redaction guards the log/trace boundary, not the answer a patient reads (§5.7).
    """
    last_sequence = -1
    while True:
        events = run_store.get_events(run_id, after_sequence=last_sequence)
        for event in events:
            yield json.dumps({"node": event.node, "output": json.loads(event.payload_json)})
            last_sequence = event.sequence

        run = run_store.get_run(run_id)
        if run is None or run.status != "running":
            break
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    status = run.status if run is not None else "not_found"
    answer = json.loads(run.answer_json) if run is not None and run.answer_json else None
    yield json.dumps({"node": "__end__", "output": {"status": status, "answer": answer}})
