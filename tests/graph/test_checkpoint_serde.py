"""The checkpoint serializer's explicit msgpack allowlist (docs/PLAN.md §5.10).

LangGraph allows unregistered checkpoint types with a warning today and will
block them in a future version, which would break resuming a held review. These
tests pin that every navigator state type round-trips as itself, and that the
allowlist really is enforced for anything else.
"""

from __future__ import annotations

from pydantic import BaseModel

from navigator.graph.checkpoint_serde import build_checkpoint_serde, navigator_state_types
from navigator.schemas.answer import Claim, PatientAnswer


class _NotAStateType(BaseModel):
    value: int


def test_every_checkpointed_state_type_is_registered() -> None:
    registered = set(navigator_state_types())
    for key in [
        ("navigator.schemas.answer", "PatientAnswer"),
        ("navigator.schemas.answer", "Claim"),
        ("navigator.schemas.preflight", "IntentAssessment"),
        ("navigator.schemas.preflight", "PolicyDecision"),
        ("navigator.schemas.scoping", "EvidenceRecord"),
        ("navigator.schemas.scoping", "SecurityEvent"),
        ("navigator.schemas.postflight", "PostFlightResult"),
    ]:
        assert key in registered


def test_navigator_types_round_trip_as_themselves() -> None:
    serde = build_checkpoint_serde()
    answer = PatientAnswer(
        body="Your A1c is recorded.",
        claims=[Claim(id="c1", text="Your A1c is recorded.", kind="clinical")],
        citations=[],
        reading_level_target=6.0,
        autonomy_level="L2_balanced",
    )

    restored = serde.loads_typed(serde.dumps_typed({"draft": answer}))

    assert isinstance(restored["draft"], PatientAnswer)
    assert restored["draft"] == answer


def test_types_outside_the_allowlist_are_not_reconstructed() -> None:
    serde = build_checkpoint_serde()
    restored = serde.loads_typed(serde.dumps_typed({"x": _NotAStateType(value=1)}))
    assert not isinstance(restored["x"], _NotAStateType)
