"""Shared value types with no dependencies of their own.

These live in the lowest layer so both the store's read models and the tool
boundary can name them without either importing the other (docs/PLAN.md §9.3).
"""

from __future__ import annotations

from typing import Literal

# Assigned deterministically by `data/build_store.py`; Synthea has no equivalent
# (docs/PLAN.md §4.3).
LiteracyLevel = Literal["basic", "intermediate", "proficient"]
