"""Structural (Protocol) types for the LLM-backed pieces nodes depend on.

Node factories accept these instead of concrete `Runnable[...]` types so a plain
test double (with just a matching `.invoke()`) can stand in without subclassing
LangChain's `Runnable` — real chains satisfy them structurally too. This is what
lets the pre-flight gate be tested with no LLM and no network.
"""

from __future__ import annotations

from typing import Protocol

from navigator.schemas.preflight import IntentAssessment


class IntentClassifierChain(Protocol):
    def invoke(self, input: dict[str, str]) -> IntentAssessment: ...
