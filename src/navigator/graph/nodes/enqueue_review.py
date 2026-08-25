"""Holds a draft for clinician review, then resumes on their decision
(docs/PLAN.md §5.10).

When post-flight decides the draft needs a human — an uncited answer that a
second pass could not ground, or a scope judgement that the draft directs a
clinical action or contradicts the record — the run does not publish. It calls
LangGraph's `interrupt()` to genuinely suspend the graph, surfacing a review
payload for a clinician, and only resumes when a human returns a decision.

`interrupt()` returns the value the reviewer resumes with
(`Command(resume=...)`): approve publishes the judged draft unchanged, edit
publishes an edited body, and decline leaves the draft held as `pending_review`,
never silently `answered`. On the first pass `interrupt()` suspends before any
of that runs, so a run with no decision yet simply halts.

`interrupt()` requires a checkpointer to suspend; this node is reachable only via
the review dispositions, which the offline test stubs never produce, so the
default test graph (no checkpointer) never hits it (§5.10).
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.types import interrupt

from navigator.graph.state import NavigatorState


def enqueue_review_node(state: NavigatorState) -> dict[str, object]:
    draft = state["draft"]
    post = state.get("post_flight")
    held = draft.model_copy(update={"disposition": "pending_review", "pending_review": True})
    review_payload: dict[str, object] = {
        "run_id": state.get("run_id"),
        "patient_id": state.get("patient_id"),
        "reason": post.trigger if post else "unknown",
        "override_action": post.override_action if post else None,
        "uncited_claim_ids": list(post.uncited_claim_ids) if post else [],
        "body": held.body,
    }
    # Suspend until a clinician resumes with a decision; the resume value is
    # returned here on the second pass (§5.10).
    decision = interrupt(review_payload)
    action = decision.get("action") if isinstance(decision, dict) else None
    if action == "approve":
        published = draft.model_copy(update={"disposition": "answered", "pending_review": False})
    elif action == "edit":
        edited_body = decision.get("edited_body") if isinstance(decision, dict) else None
        body = str(edited_body) if edited_body else draft.body
        published = draft.model_copy(
            update={"body": body, "disposition": "answered", "pending_review": False}
        )
    else:
        # decline (or an unrecognised decision): the draft stays held, never
        # promoted to answered on a reviewer's silence.
        published = held
    return {"published": published}


def build_enqueue_review_node() -> Callable[[NavigatorState], dict[str, object]]:
    return enqueue_review_node
