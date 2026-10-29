import json
import time
from collections.abc import AsyncIterator
from functools import partial
from typing import Any

from zarreh_agentkit.runs import replay_and_tail
from zarreh_agentkit.serialization import stream_graph_events

from navigator.store.run_store import RunStore

__all__ = ["stream_conversation_events", "stream_graph_events"]


def stream_conversation_events(
    run_store: RunStore, run_id: str, max_wait_seconds: float | None = None
) -> AsyncIterator[str]:
    """Replays every event already persisted for a conversation, then — while the
    run is still executing — tails newly-appended events until it reaches a
    terminal status. Works identically whether the patient connects the instant a
    run starts or reconnects long after it finished (docs/PLAN.md §5.8).

    These events are the patient's own record and are deliberately not redacted;
    redaction guards the log/trace boundary, not the answer a patient reads (§5.7).

    ``max_wait_seconds`` bounds the tail: a run that never reaches a terminal
    status ends the stream with its current status rather than holding the
    connection open forever.
    """
    deadline = None if max_wait_seconds is None else time.monotonic() + max_wait_seconds

    def poll_end() -> dict[str, Any] | None:
        run = run_store.get_run(run_id)
        still_running = run is not None and run.status == "running"
        timed_out = deadline is not None and time.monotonic() >= deadline
        if still_running and not timed_out:
            return None
        status = run.status if run is not None else "not_found"
        answer = json.loads(run.answer_json) if run is not None and run.answer_json else None
        return {"status": status, "answer": answer}

    return replay_and_tail(partial(run_store.get_events, run_id), poll_end)
