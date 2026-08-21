"""Generate the editable safety policy rule table.

The source notebook's best idea was policy as a **data table the clinical owner
can edit without a deploy**, and it survives the rewrite (docs/PLAN.md §3.8).
What changes is the evidence standard: every escalation rule here cites a
published, patient-facing source **and quotes it**, because the author is not a
clinician and his judgement is not an acceptable source for the highest-
consequence content in the app (§4.4).

The build fails on an escalation rule with no citation. That is launch gate
§11.8, enforced at the point the table is written rather than checked later.

What this file is *not*: it is not the matcher. Patterns here are compiled by
`guardrails/rule_engine.py` in Phase 3, which adds the negation and attribution
handling that makes canonical case 12 — "my discharge note says to watch for
chest pain" — an ordinary answer rather than an escalation. Substring matching
is not a guardrail (§3.2, D-A3-2).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_DB = DATA_DIR / "policy.db"

RULE_TABLE_VERSION = 1

SCHEMA = """
CREATE TABLE policy_rules (
    rule_id      TEXT PRIMARY KEY,
    action       TEXT NOT NULL,
    band         TEXT NOT NULL,
    category     TEXT NOT NULL,
    pattern      TEXT NOT NULL,
    description  TEXT NOT NULL,
    template_id  TEXT NOT NULL,
    severity     INTEGER NOT NULL,
    source_name  TEXT,
    source_url   TEXT,
    source_quote TEXT,
    version      INTEGER NOT NULL,
    enabled      INTEGER NOT NULL
);

CREATE INDEX idx_rules_action ON policy_rules(action, enabled);
"""

# Severity precedence, fixed and deterministic (§5.2). Higher wins, and where the
# deterministic screen and the classifier disagree the more restrictive wins.
SEVERITY = {
    "direct_to_emergency_care": 50,
    "crisis": 45,
    "out_of_scope": 30,
    "clinician_review": 20,
    "allow": 0,
}

ESCALATING_ACTIONS = frozenset({"direct_to_emergency_care", "crisis"})


@dataclass(frozen=True)
class Rule:
    rule_id: str
    action: str
    band: str
    category: str
    pattern: str
    description: str
    template_id: str
    source_name: str | None = None
    source_url: str | None = None
    source_quote: str | None = None
    enabled: bool = True

    @property
    def severity(self) -> int:
        return SEVERITY[self.action]


HEART_ATTACK = (
    "MedlinePlus — Heart Attack",
    "https://medlineplus.gov/heartattack.html",
    "That's why it's important to know the symptoms of a heart attack and call 911 if you or "
    "someone else is having them. You should call, even if you are not sure that it is a heart "
    "attack.",
)
STROKE = (
    "MedlinePlus — Stroke",
    "https://medlineplus.gov/stroke.html",
    "If you think that you or someone else is having a stroke, call 911 right away.",
)
ANAPHYLAXIS = (
    "MedlinePlus — Anaphylaxis",
    "https://medlineplus.gov/anaphylaxis.html",
    "If someone is having a serious allergic reaction, call 911.",
)
SUICIDE = (
    "MedlinePlus — Suicide and Suicidal Thoughts",
    "https://medlineplus.gov/suicide.html",
    "If you or someone you know has the warning signs for suicide, get help right away, "
    "especially if there is a change in behavior. If it is an emergency, dial 911.",
)

RULES: tuple[Rule, ...] = (
    # ---- Emergency direction. Never "triage": the system detects a pattern on a
    # published list and directs to care that can actually assess it (§3.7).
    Rule(
        "rf-cardiac-chest-pain",
        "direct_to_emergency_care",
        "escalate",
        "cardiac",
        r"\b(chest (pain|pressure|tightness|discomfort)|pressure in (my )?chest)\b",
        "Chest pain, pressure, tightness or discomfort.",
        "emergency_cardiac",
        *HEART_ATTACK,
    ),
    Rule(
        "rf-cardiac-radiating",
        "direct_to_emergency_care",
        "escalate",
        "cardiac",
        r"\b(pain|numb\w*|tingling)\b.{0,40}\b(left arm|jaw|shoulder|back)\b",
        "Pain or numbness radiating to the arm, jaw, shoulder or back.",
        "emergency_cardiac",
        *HEART_ATTACK,
    ),
    Rule(
        "rf-cardiac-associated",
        "direct_to_emergency_care",
        "escalate",
        "cardiac",
        r"\b(cold sweat|breaking out in a sweat|short(ness)? of breath|lightheaded)\b",
        "Cold sweat, shortness of breath or light-headedness.",
        "emergency_cardiac",
        *HEART_ATTACK,
    ),
    Rule(
        "rf-stroke-face-arm-speech",
        "direct_to_emergency_care",
        "escalate",
        "stroke",
        r"\b(face (is )?droop\w*|slurred speech|can'?t speak|sudden.{0,20}weakness on one side)\b",
        "Facial droop, slurred speech or sudden one-sided weakness.",
        "emergency_stroke",
        *STROKE,
    ),
    Rule(
        "rf-stroke-sudden-neuro",
        "direct_to_emergency_care",
        "escalate",
        "stroke",
        r"\bsudden\b.{0,30}\b(numbness|confusion|trouble seeing|severe headache|loss of balance)\b",
        "Sudden numbness, confusion, vision loss, severe headache or loss of balance.",
        "emergency_stroke",
        *STROKE,
    ),
    Rule(
        "rf-anaphylaxis",
        "direct_to_emergency_care",
        "escalate",
        "anaphylaxis",
        r"\b(throat (is )?(closing|swelling)|can'?t breathe|trouble swallowing|"
        r"swelling of (my )?(lips|tongue|throat))\b",
        "Airway swelling or breathing difficulty suggesting a serious allergic reaction.",
        "emergency_anaphylaxis",
        *ANAPHYLAXIS,
    ),
    # ---- Crisis. A separate path from medical emergency, because the correct
    # resource and the correct wording both differ (§4.4).
    Rule(
        "rf-self-harm",
        "crisis",
        "escalate",
        "self_harm",
        r"\b(kill myself|end my life|suicid\w*|don'?t want to (be here|live)|hurt myself)\b",
        "Statements indicating suicidal thoughts or self-harm.",
        "crisis_988",
        *SUICIDE,
    ),
    # ---- Out of scope. No published source is required or appropriate: these are
    # scope boundaries this project set, not clinical findings. The distinction is
    # itself worth keeping visible in the table.
    Rule(
        "scope-dosing",
        "out_of_scope",
        "escalate",
        "dosing",
        r"\b(how (much|many)|what dose|dosage|how often should i take|can i take (more|another))\b",
        "Requests for a dose or dosing frequency.",
        "out_of_scope_dosing",
    ),
    Rule(
        "scope-stop-or-change-medication",
        "out_of_scope",
        "escalate",
        "medication_change",
        r"\b(should i (stop|quit|come off|cut back)|stop taking|is it ok(ay)? to (stop|come off)|"
        r"double (up on )?my dose)\b",
        "Requests to start, stop or change a medication.",
        "out_of_scope_medication_change",
    ),
    Rule(
        "scope-diagnosis-request",
        "out_of_scope",
        "recommend",
        "diagnosis_request",
        r"\b(do i have|what'?s wrong with me|is this (cancer|lupus|diabetes)|am i (dying|sick))\b",
        "Requests for a diagnosis.",
        "out_of_scope_diagnosis",
    ),
    Rule(
        "scope-out-of-domain",
        "out_of_scope",
        "inform",
        "out_of_domain",
        r"\b(weather|stock price|sports score|movie|restaurant|who won)\b",
        "Questions outside health entirely.",
        "out_of_scope_general",
    ),
    # ---- Clinician review. Decision-adjacent questions: answerable in principle,
    # but the answer is a recommendation, so it goes to a human at L1/L2 (§5.9).
    Rule(
        "review-interaction",
        "clinician_review",
        "recommend",
        "interaction",
        r"\b(can i take .{0,40}with|interact\w*|safe to take .{0,30}(with|and)|mix .{0,20}with)\b",
        "Drug-interaction and combination questions.",
        "review_interaction",
    ),
    Rule(
        "review-symptom-management",
        "clinician_review",
        "recommend",
        "symptom_management",
        r"\b(what should i do about|how do i treat|"
        r"should i (see|call) (a |my )?(doctor|provider))\b",
        "Requests for management advice about a symptom.",
        "review_symptom_management",
    ),
    Rule(
        "review-pregnancy-breastfeeding",
        "clinician_review",
        "recommend",
        "pregnancy",
        r"\b(pregnan\w*|breastfeed\w*|nursing)\b",
        "Questions involving pregnancy or breastfeeding.",
        "review_pregnancy",
    ),
)


def validate(rules: tuple[Rule, ...]) -> None:
    """Fail the build on an uncited escalation rule or a duplicate id."""
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            raise SystemExit(f"Duplicate rule id: {rule.rule_id}")
        seen.add(rule.rule_id)
        if rule.action not in SEVERITY:
            raise SystemExit(f"{rule.rule_id}: unknown action {rule.action!r}")
        if rule.action in ESCALATING_ACTIONS and not (rule.source_url and rule.source_quote):
            raise SystemExit(
                f"{rule.rule_id}: escalation rules must cite and quote a published "
                "patient-facing source (docs/PLAN.md §4.4, launch gate §11.8)."
            )


def build(db_path: Path) -> dict[str, int]:
    validate(RULES)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO policy_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rule.rule_id,
                    rule.action,
                    rule.band,
                    rule.category,
                    rule.pattern,
                    rule.description,
                    rule.template_id,
                    rule.severity,
                    rule.source_name,
                    rule.source_url,
                    rule.source_quote,
                    RULE_TABLE_VERSION,
                    int(rule.enabled),
                )
                for rule in RULES
            ],
        )
        connection.commit()
    finally:
        connection.close()

    cited = sum(1 for rule in RULES if rule.source_url)
    return {
        "rules": len(RULES),
        "escalating": sum(1 for rule in RULES if rule.action in ESCALATING_ACTIONS),
        "cited": cited,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    print("generate_policy_rules")
    counts = build(args.db)
    print(f"  rules       {counts['rules']} at table version {RULE_TABLE_VERSION}")
    print(f"  escalating  {counts['escalating']}, every one citing and quoting a published source")
    print(f"  cited       {counts['cited']} rules carry a source URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
