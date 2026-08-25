from functools import lru_cache
from pathlib import Path

from navigator.graph.builder import SkeletonGraph, build_skeleton_graph
from navigator.settings import Settings, get_settings
from navigator.store import EducationStore, PolicyStore, RecordStore
from navigator.tools import ScopedToolExecutor, ToolRegistry, build_registry


def settings_dependency() -> Settings:
    return get_settings()


@lru_cache
def get_compiled_graph() -> SkeletonGraph:
    """Single compiled-graph instance, shared across requests."""
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
