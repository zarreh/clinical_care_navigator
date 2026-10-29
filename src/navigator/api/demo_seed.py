"""Seeds the clinician review queue with demonstration items.

A held answer only appears when post-flight refuses to publish a draft, which a
well-behaved model does rarely. To demonstrate the clinician's role on demand,
this drives four *scripted* drafts through the real graph, the real post-flight
checks and the real checkpoint store. Nothing is faked at the storage layer, so
each item genuinely pauses at `enqueue_review` and a decision in the UI genuinely
resumes it.

What is scripted is only the model's output: the drafts and the judge's verdicts
are fixed text, written from the patient's real A1c result so they are accurate
about the record. No model is called, so this needs no API key and costs nothing.

Run it with ``make seed-reviews`` (or, in Docker,
``docker compose -f compose.prod.yaml exec navigator-api python -m navigator.api.demo_seed``).
Re-running is safe: a case already seeded is skipped. ``--again`` adds a fresh
copy of each case, for replaying the demo after the items have been decided.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.tool import ToolCall
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from navigator.api.personas import personas_for
from navigator.api.run_executor import execute_conversation
from navigator.graph.builder import build_navigator_graph
from navigator.graph.checkpoint_serde import build_checkpoint_serde
from navigator.schemas.answer import Citation, Claim, PatientAnswer
from navigator.schemas.postflight import ExtractedClaims, ScopeJudgement
from navigator.schemas.preflight import IntentAssessment
from navigator.settings import Settings, get_settings
from navigator.store import RecordStore, ReviewQueue, RunStore
from navigator.store.models import Observation

_A1C = "hemoglobin A1c"
_TOOL_CALL_ID = "demo-call-1"
# Above this, an A1c is outside the usual reference range (prediabetes and up).
_A1C_UPPER_NORMAL = 5.6


@dataclass(frozen=True)
class DemoCase:
    slug: str
    question: str
    why_held: str
    body: str
    claims: tuple[Claim, ...]
    judgement: ScopeJudgement
    # False when the scripted AI finds nothing to look up, so it has no evidence to cite.
    lookup: bool = True


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def build_cases(a1c: Observation) -> list[DemoCase]:
    """Four drafts post-flight will hold, each for a different reason. The text is
    built from the patient's actual A1c so it is accurate about the record, except
    where a case is *meant* to contradict it."""
    value = a1c.value_number or 0.0
    reading = f"{_fmt(value)} {a1c.units or '%'}".strip()
    above_range = value > _A1C_UPPER_NORMAL
    cite = [_TOOL_CALL_ID]

    wrong_range = "within" if above_range else "above"
    return [
        DemoCase(
            slug="directs-action",
            question="What does my latest A1c result mean for me?",
            why_held=(
                "The scope judge flagged the draft for telling the patient what clinical "
                "action to take."
            ),
            body=(
                f"Your most recent A1c was {reading}. "
                "You should ask your doctor to raise your medication dose at your next visit."
            ),
            claims=(
                Claim(
                    id="c1",
                    text=f"Your most recent A1c was {reading}.",
                    kind="clinical",
                    evidence_refs=cite,
                ),
                Claim(
                    id="c2",
                    text="You should ask your doctor to raise your medication dose.",
                    kind="clinical",
                    evidence_refs=cite,
                ),
            ),
            judgement=ScopeJudgement(
                directs_clinical_action=True,
                spans={"directs_clinical_action": "ask your doctor to raise your medication dose"},
            ),
        ),
        DemoCase(
            slug="contradicts-record",
            question="Is my latest blood sugar test okay?",
            why_held="The scope judge flagged the draft as contradicting what the record shows.",
            body=(
                f"Your most recent A1c was {reading}, which is {wrong_range} the usual range. "
                "There is nothing here to follow up on."
            ),
            claims=(
                Claim(
                    id="c1",
                    text=f"Your most recent A1c was {reading}.",
                    kind="clinical",
                    evidence_refs=cite,
                ),
                Claim(
                    id="c2",
                    text=f"Your A1c is {wrong_range} the usual range.",
                    kind="clinical",
                    evidence_refs=cite,
                ),
            ),
            judgement=ScopeJudgement(
                contradicts_record=True,
                spans={"contradicts_record": f"{wrong_range} the usual range"},
            ),
        ),
        DemoCase(
            slug="uncited-claim",
            question="How has my A1c changed over the years?",
            why_held=(
                "A clinical claim still had no evidence behind it after the AI was sent back "
                "to the record once, so post-flight would not publish it."
            ),
            body=(
                f"Your most recent A1c was {reading}. "
                "Your A1c has been rising steadily over the past few years."
            ),
            claims=(
                Claim(
                    id="c1",
                    text=f"Your most recent A1c was {reading}.",
                    kind="clinical",
                    evidence_refs=cite,
                ),
                Claim(
                    id="c2",
                    text="Your A1c has been rising steadily over the past few years.",
                    kind="clinical",
                    evidence_refs=[],
                ),
            ),
            judgement=ScopeJudgement(),
        ),
        DemoCase(
            slug="no-information",
            question="What is the bad cholesterol?",
            why_held=(
                "The AI found nothing in the record to answer a general question, so its only "
                "claim was 'I don't have information', which has no evidence to cite. After one "
                "retry post-flight handed it to a clinician. This is a safe reply, so approving "
                "it as written is the usual decision."
            ),
            body=(
                "I don't have information about bad cholesterol in your record. "
                "Please ask your care team for more details."
            ),
            claims=(
                Claim(
                    id="c1",
                    text="I don't have information about bad cholesterol in your record.",
                    kind="clinical",
                    evidence_refs=[],
                ),
                Claim(
                    id="c2",
                    text="Please ask your care team for more details.",
                    kind="navigational",
                    evidence_refs=[],
                ),
            ),
            judgement=ScopeJudgement(),
            lookup=False,
        ),
    ]


class _ScriptedIntent:
    def __init__(self, question: str) -> None:
        self._question = question

    def invoke(self, input: dict[str, str]) -> IntentAssessment:
        return IntentAssessment(
            question_class="lab_education",
            red_flags=[],
            confidence=0.9,
            rationale_span=self._question[:40],
        )


class _ScriptedExplainer:
    """Looks up the A1c once (unless told not to), then says it is done, and keeps
    saying so if post-flight sends it back for more evidence."""

    def __init__(self, patient_id: str, *, lookup: bool = True) -> None:
        self._patient_id = patient_id
        self._called = not lookup

    def invoke(self, messages: Sequence[BaseMessage]) -> BaseMessage:
        if not self._called:
            self._called = True
            return AIMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        name="get_labs",
                        args={"patient_id": self._patient_id, "analyte": _A1C},
                        id=_TOOL_CALL_ID,
                        type="tool_call",
                    )
                ],
            )
        return AIMessage(content="done")


class _ScriptedWriter:
    def __init__(self, case: DemoCase) -> None:
        self._case = case

    def invoke(self, input: dict[str, object]) -> PatientAnswer:
        return PatientAnswer(
            body=self._case.body,
            claims=list(self._case.claims),
            citations=[
                Citation(
                    claim_id=c.id,
                    tool_call_id=c.evidence_refs[0],
                    title="Your own lab record",
                )
                for c in self._case.claims
                if c.evidence_refs
            ],
            reading_level_target=0.0,
            autonomy_level="L2_balanced",
        )


class _ScriptedClaimExtractor:
    def __init__(self, case: DemoCase) -> None:
        self._case = case

    def invoke(self, input: dict[str, object]) -> ExtractedClaims:
        return ExtractedClaims(claims=list(self._case.claims))


class _ScriptedJudge:
    def __init__(self, case: DemoCase) -> None:
        self._case = case

    def invoke(self, input: dict[str, object]) -> ScopeJudgement:
        return self._case.judgement


class NoA1cError(RuntimeError):
    """No patient in the record store has an A1c result to build a demo from."""


def pick_patient(store: RecordStore, preferred: str) -> tuple[str, Observation]:
    """The demo patient (if configured), else the first persona with an A1c result
    (the full-record persona, i.e. the richest history), else any patient with one."""
    if preferred:
        candidates = [preferred]
    else:
        persona_ids = [p.patient_id for p in personas_for(store)]
        candidates = persona_ids + [i for i in store.patient_ids() if i not in persona_ids]
    for patient_id in candidates:
        for obs in store.observations(patient_id, analyte=_A1C, limit=1):
            if obs.value_number is not None:
                return patient_id, obs
    raise NoA1cError(
        "No patient has an A1c result to build the demo from. Run `make data` first, "
        "or unset NAVIGATOR_DEMO_PATIENT_ID."
    )


async def seed(settings: Settings, *, again: bool = False) -> list[tuple[DemoCase, str, str]]:
    """Seeds the queue. Returns (case, run id, outcome) per case, where outcome is
    the run's status, or "skipped" if it was already seeded."""
    # Scripted runs must not be sent to an external tracing service.
    offline = settings.model_copy(update={"langsmith_api_key": ""})
    record_store = RecordStore(Path(offline.record_db_path))
    patient_id, a1c = pick_patient(record_store, offline.demo_patient_id)
    run_store = RunStore(Path(offline.run_store_path))
    review_queue = ReviewQueue(Path(offline.run_store_path))
    suffix = f"-{secrets.token_hex(2)}" if again else ""

    results: list[tuple[DemoCase, str, str]] = []
    Path(offline.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(offline.checkpoint_db_path) as conn:
        saver = AsyncSqliteSaver(conn, serde=build_checkpoint_serde())
        for case in build_cases(a1c):
            run_id = f"demo-{case.slug}{suffix}"
            if run_store.get_run(run_id) is not None:
                results.append((case, run_id, "skipped"))
                continue
            graph = build_navigator_graph(
                offline,
                intent_chain=_ScriptedIntent(case.question),
                explainer=_ScriptedExplainer(patient_id, lookup=case.lookup),
                answer_writer_chain=_ScriptedWriter(case),
                claim_extractor_chain=_ScriptedClaimExtractor(case),
                scope_judge_chain=_ScriptedJudge(case),
                checkpointer=saver,
            )
            run_store.create_run(run_id, case.question, patient_id)
            await execute_conversation(
                run_id, case.question, patient_id, graph, run_store, review_queue, offline
            )
            run = run_store.get_run(run_id)
            results.append((case, run_id, run.status if run is not None else "unknown"))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument(
        "--again",
        action="store_true",
        help="add a fresh copy of each case even if it was seeded before",
    )
    args = parser.parse_args()
    try:
        results = asyncio.run(seed(get_settings(), again=args.again))
    except NoA1cError as exc:
        raise SystemExit(str(exc)) from exc

    for case, _run_id, status in results:
        print(f"{status:>15}  {case.slug:<19} {case.question}")
        if status == "pending_review":
            print(f"{'':>15}  -> held because: {case.why_held}")
    held = sum(1 for _, _, s in results if s == "pending_review")
    skipped = sum(1 for _, _, s in results if s == "skipped")
    print(
        f"\n{held} item(s) added to the clinician review queue"
        + (f", {skipped} already seeded (use --again for fresh copies)" if skipped else "")
        + ".\nThese drafts are scripted demonstrations, not model output. "
        "Open /reviews to decide them."
    )


if __name__ == "__main__":
    main()
