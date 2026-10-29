"""The checkpoint serializer with an explicit msgpack allowlist (docs/PLAN.md §5.10).

LangGraph deserializes checkpointed graph state with msgpack. Types it does not
know are allowed with a warning today and "will be blocked in a future version",
which would silently break resuming a held review after an upgrade. Registering
every Pydantic model in ``navigator.schemas`` makes the allowlist explicit: our
own state types round-trip, and anything else outside LangGraph's built-in safe
set is refused rather than reconstructed from the database.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

import navigator.schemas


def navigator_state_types() -> list[tuple[str, str]]:
    """(module, class name) for every Pydantic model defined in navigator.schemas."""
    found: set[tuple[str, str]] = set()
    for info in pkgutil.iter_modules(navigator.schemas.__path__, f"{navigator.schemas.__name__}."):
        module = importlib.import_module(info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseModel) and obj.__module__ == module.__name__:
                found.add((obj.__module__, obj.__name__))
    return sorted(found)


def build_checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=navigator_state_types())
