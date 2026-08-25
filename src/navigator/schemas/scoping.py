"""Typed records the tool executor produces (docs/PLAN.md §5.4).

Three models, and the reason each exists is a defect in the source notebook:

`ToolScope` is the registry the agent is bound to, **selected by the gate
decision** rather than filtered afterwards (§3.3). A `refuse` or
`escalate_clinician` decision hands the executor a scope whose
`allowed_tool_names` excludes every patient tool, so minimum-necessary is a
property of control flow, not of a prompt.

`EvidenceRecord` makes every tool result addressable by its `tool_call_id`. The
source appended free-text `ToolMessage`s and hoped the model re-parsed them; a
typed record keyed by call id is what lets post-flight link a claim to the exact
evidence it rests on (§3.5).

`SecurityEvent` is the fix for scoping being enforced *silently* (§3.4). A model
that just tried to read another patient's chart must not leave the same audit
trail as one that did not.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SecurityEventKind = Literal[
    "cross_patient_overwrite",
    "blocked_unknown_tool",
    "out_of_scope_tool",
]


class ToolScope(BaseModel):
    """The tools a run may reach, and how many rows each may return.

    Selected by the pre-flight gate. A restricted scope is refused *at the
    executor*, so a tool outside the scope is unreachable rather than merely
    discouraged.
    """

    model_config = ConfigDict(frozen=True)

    allowed_tool_names: frozenset[str]
    row_cap: int = Field(gt=0)


class EvidenceRecord(BaseModel):
    """One executed tool call, addressable by `tool_call_id`.

    `args_after_scoping` records the arguments the executor actually used --
    after the patient-id overwrite and the row-cap clamp -- not what the model
    requested, so the audit trail reflects what really happened.
    """

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    tool_name: str
    args_after_scoping: dict[str, object]
    result: dict[str, object]
    retrieved_at: str


class SecurityEvent(BaseModel):
    """A scoping control that fired, persisted and surfaced in the trace.

    `requested` is what the model asked for; `enforced` is what the executor
    substituted or the fact that it blocked the call. An attempted
    cross-patient read is the single most interesting event this system logs.
    """

    model_config = ConfigDict(frozen=True)

    kind: SecurityEventKind
    tool_name: str
    requested: str
    enforced: str
    run_id: str
    at: str
