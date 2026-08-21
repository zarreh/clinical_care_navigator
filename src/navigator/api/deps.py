from functools import lru_cache

from navigator.graph.builder import SkeletonGraph, build_skeleton_graph
from navigator.settings import Settings, get_settings


def settings_dependency() -> Settings:
    return get_settings()


@lru_cache
def get_compiled_graph() -> SkeletonGraph:
    """Single compiled-graph instance, shared across requests."""
    return build_skeleton_graph()
