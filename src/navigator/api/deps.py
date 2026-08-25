"""FastAPI dependencies: process-shared singletons for the stores, the scoped
tool executor, the real navigator graph (with a SQLite checkpointer), and the
run/review persistence used by the conversation and review APIs (docs/PLAN.md
§5.8, §5.10).

Everything here is `lru_cache`d so a connection or a compiled graph is opened
once and injected, never rebuilt per request. The record/education/policy stores
are read-only and connect with ``check_same_thread=False``; the run store, review
queue and checkpointer are writable and likewise thread-safe for the single
process this demo runs in.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Request

from navigator.graph.builder import (
    NavigatorGraph,
    SkeletonGraph,
    build_navigator_graph,
    build_skeleton_graph,
)
from navigator.guardrails.redaction import PhiRedactor
from navigator.settings import Settings, get_settings
from navigator.store import (
    EducationStore,
    PolicyStore,
    RecordStore,
    ReviewQueue,
    RunStore,
)
from navigator.tools import ScopedToolExecutor, ToolRegistry, build_registry


def settings_dependency() -> Settings:
    return get_settings()


@lru_cache
def get_compiled_graph() -> SkeletonGraph:
    """The Phase 0 skeleton graph, kept as the streaming proof (docs/PLAN.md §7)."""
    return build_skeleton_graph()


@lru_cache
def get_record_store() -> RecordStore:
    """One read-only record-store connection, shared across requests.

    Opened once and injected, not reopened per tool call as the source notebook
    did (docs/PLAN.md §3.2). Safe to share because it is read-only and connects
    with ``check_same_thread=False``.
    """
    return RecordStore(Path(get_settings().record_db_path))


@lru_cache
def get_education_store() -> EducationStore:
    """One read-only education-store connection, shared across requests."""
    return EducationStore(Path(get_settings().education_db_path))


@lru_cache
def get_policy_store() -> PolicyStore:
    """One read-only policy-store connection, shared across requests."""
    return PolicyStore(Path(get_settings().policy_db_path))


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """The eleven tools, bound once to the shared store connections."""
    return build_registry(get_record_store(), get_education_store())


def get_tool_executor() -> ScopedToolExecutor:
    """The scoped executor over the shared registry."""
    return ScopedToolExecutor(get_tool_registry())


@lru_cache
def get_run_store() -> RunStore:
    """Durable conversation store (runs, events, per-node costs)."""
    return RunStore(Path(get_settings().run_store_path))


@lru_cache
def get_review_queue() -> ReviewQueue:
    """Clinician review queue, sharing the run-store database (own table)."""
    return ReviewQueue(Path(get_settings().run_store_path))


def get_navigator_graph(request: Request) -> NavigatorGraph:
    """The real navigator graph, compiled once against the app's async SQLite
    checkpointer (created in the lifespan) and cached on ``app.state``.

    No chains are injected, so the builder constructs the production LLM pieces
    from settings (docs/PLAN.md §5.3); it is built lazily on the first real
    request so import and test runs never construct the models. The checkpointer
    keeps each conversation's state under its ``thread_id`` so a suspended review
    resumes from disk after a reviewer decision arrives on a later request
    (docs/PLAN.md §5.10).
    """
    state = request.app.state
    graph = getattr(state, "navigator_graph", None)
    if graph is None:
        graph = build_navigator_graph(get_settings(), checkpointer=state.checkpointer)
        state.navigator_graph = graph
    return graph


@lru_cache
def get_phi_redactor() -> PhiRedactor:
    """A redactor seeded from the store's own patients, for the log/trace
    boundary (docs/PLAN.md §5.7). Built from the record store so the falsifiable
    test can assert against the store's real values."""
    store = get_record_store()
    patients = [p for p in (store.get_patient(pid) for pid in store.patient_ids()) if p is not None]
    return PhiRedactor.from_patients(patients)
