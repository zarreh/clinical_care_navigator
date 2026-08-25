"""Intake: loads the patient header only (docs/PLAN.md §5.1).

Reads id, literacy level, language and the autonomy setting — **no clinical
content**. That this node never touches a clinical row is a deliberate privacy
property: the intake and the intent classifier both run before any clinical
content is read, and the docs say so.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from navigator.graph.state import NavigatorState
from navigator.settings import Settings
from navigator.store import RecordStore


def build_intake_node(
    record_store: RecordStore, settings: Settings
) -> Callable[[NavigatorState], dict[str, object]]:
    def intake_node(state: NavigatorState) -> dict[str, object]:
        patient = record_store.get_patient(state["patient_id"])
        literacy = patient.health_literacy_level if patient else "intermediate"
        language = patient.language if patient else "en"
        return {
            "literacy_level": literacy,
            "language": language,
            "autonomy_level": settings.autonomy_level,
            "started_at": time.time(),
            "messages": [],
            "evidence": [],
            "security_events": [],
            "tool_call_count": 0,
        }

    return intake_node
