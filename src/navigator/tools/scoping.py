"""The scoped tool executor -- where the source notebook's four defects are fixed.

The source ran tool calls in a `tool_exec_node` that overwrote `patient_id`
silently, capped a `limit` inline, blocked unknown tools with a bare string, and
appended free-text `ToolMessage`s. Each of those is a control that should be
visible and testable. This executor keeps the good instincts and makes them
auditable:

- **Allowlist at the executor.** A call to a tool outside the run's `ToolScope`
  is refused here, not discouraged in a prompt -- and a non-`allow` gate hands
  in a scope from which patient tools are simply absent (docs/PLAN.md §3.3).
- **Patient scoping is recorded.** Forcing `patient_id` to the session patient
  emits a typed `SecurityEvent` when the model asked for a different one; an
  attempted cross-patient read no longer leaves the same trail as a benign call
  (§3.4, canonical case 6).
- **Row caps are a security control.** `limit` is clamped to the scope's
  `row_cap`, which is a minimum-necessary control as much as a cost one (§5.5).
- **Every result is addressable.** Each call yields an `EvidenceRecord` keyed by
  its `tool_call_id`, so post-flight can bind a claim to the exact evidence it
  rests on rather than re-parsing a string (§3.5).

This module runs with no LLM and no network: given tool calls, a patient id and
a scope, it executes purely against the injected stores.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from langchain_core.messages import ToolMessage
from langchain_core.messages.tool import ToolCall
from pydantic import BaseModel

from navigator.schemas.scoping import EvidenceRecord, SecurityEvent, ToolScope
from navigator.tools.registry import ToolRegistry


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ToolExecution:
    """The full, auditable outcome of executing a batch of tool calls.

    `messages` feed back into the model's context; `evidence` and
    `security_events` are the persisted, trace-surfaced record of what actually
    happened -- kept separate because they answer different questions.
    """

    messages: list[ToolMessage] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    security_events: list[SecurityEvent] = field(default_factory=list)


class ScopedToolExecutor:
    """Executes tool calls under a `ToolScope`, forcing the session patient."""

    def __init__(self, registry: ToolRegistry, *, now: Callable[[], str] = _utc_now) -> None:
        self._registry = registry
        self._now = now

    def execute(
        self,
        tool_calls: Sequence[ToolCall],
        *,
        patient_id: str,
        scope: ToolScope,
        run_id: str,
    ) -> ToolExecution:
        result = ToolExecution()
        for call in tool_calls:
            self._execute_one(call, patient_id=patient_id, scope=scope, run_id=run_id, out=result)
        return result

    def _execute_one(
        self,
        call: ToolCall,
        *,
        patient_id: str,
        scope: ToolScope,
        run_id: str,
        out: ToolExecution,
    ) -> None:
        name = call["name"]
        call_id = call.get("id") or ""
        args: dict[str, object] = dict(call.get("args") or {})

        # 1. Allowlist: a tool that does not exist in the registry at all.
        if name not in self._registry.tools:
            out.security_events.append(
                SecurityEvent(
                    kind="blocked_unknown_tool",
                    tool_name=name,
                    requested=name,
                    enforced="blocked",
                    run_id=run_id,
                    at=self._now(),
                )
            )
            out.messages.append(self._error_message(name, call_id, f"Blocked unknown tool: {name}"))
            return

        # 2. Scope: a real tool the current decision does not permit.
        if name not in scope.allowed_tool_names:
            out.security_events.append(
                SecurityEvent(
                    kind="out_of_scope_tool",
                    tool_name=name,
                    requested=name,
                    enforced="blocked",
                    run_id=run_id,
                    at=self._now(),
                )
            )
            out.messages.append(
                self._error_message(name, call_id, f"Tool {name} is out of scope for this request")
            )
            return

        # 3. Patient scoping: overwrite, and record a mismatch.
        if name in self._registry.patient_scoped_names:
            requested = args.get("patient_id")
            if requested is not None and str(requested) != patient_id:
                out.security_events.append(
                    SecurityEvent(
                        kind="cross_patient_overwrite",
                        tool_name=name,
                        requested=str(requested),
                        enforced=patient_id,
                        run_id=run_id,
                        at=self._now(),
                    )
                )
            args["patient_id"] = patient_id

        # 4. Row cap: clamp limit to the scope, whether or not the model set one.
        if name in self._registry.limit_names:
            args["limit"] = self._clamp_limit(args.get("limit"), scope.row_cap)

        # 5. Execute purely against the injected store.
        model = self._registry.tools[name].invoke(args)
        assert isinstance(model, BaseModel)  # noqa: S101 - tool return contract
        out.evidence.append(
            EvidenceRecord(
                tool_call_id=call_id,
                tool_name=name,
                args_after_scoping=args,
                result=model.model_dump(mode="json"),
                retrieved_at=self._now(),
            )
        )
        out.messages.append(
            ToolMessage(content=model.model_dump_json(), name=name, tool_call_id=call_id)
        )

    @staticmethod
    def _clamp_limit(raw: object, row_cap: int) -> int:
        if raw is None:
            return row_cap
        try:
            requested: int = int(raw)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return row_cap
        return max(1, min(requested, row_cap))

    @staticmethod
    def _error_message(name: str, call_id: str, message: str) -> ToolMessage:
        return ToolMessage(content=message, name=name, tool_call_id=call_id, status="error")
