"""Loads versioned prompt files by id — never inline strings in a node or chain
(docs/PLAN.md §3.6), so a prompt can be diffed, versioned, and later optimised
(A10) without touching code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load_prompt(prompt_id: str) -> str:
    path = _PROMPTS_DIR / f"{prompt_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file for id {prompt_id!r} at {path}")
    return path.read_text().strip()
