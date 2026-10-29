"""Loads versioned prompt files by id — never inline strings in a node or chain
(docs/PLAN.md §3.6), so a prompt can be diffed, versioned, and later optimised
(A10) without touching code.
"""

from pathlib import Path

from zarreh_agentkit.prompts import PromptLoader

_LOADER = PromptLoader(Path(__file__).parent)
load_prompt = _LOADER.load
