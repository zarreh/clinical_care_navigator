"""Publish is a byte-identical, deterministic copy of the judged draft (§5.3)."""

from __future__ import annotations

from navigator.graph.nodes.publish import publish_node
from navigator.schemas.answer import Citation, Claim, PatientAnswer


def _draft() -> PatientAnswer:
    return PatientAnswer(
        body="Your LDL cholesterol result is recorded in your chart.",
        claims=[Claim(id="c1", text="recorded", kind="clinical", evidence_refs=["call-1"])],
        citations=[Citation(claim_id="c1", tool_call_id="call-1")],
        reading_level_target=8.0,
        reading_level_measured=7.2,
        autonomy_level="L2_balanced",
    )


def test_published_body_is_byte_identical() -> None:
    draft = _draft()
    out = publish_node({"draft": draft})
    published = out["published"]
    assert isinstance(published, PatientAnswer)
    # Nothing is silently reworded after the checks that approved it.
    assert published.body == draft.body
    assert published.claims == draft.claims
    assert published.citations == draft.citations
    assert published.disposition == "answered"
    assert published.pending_review is False
