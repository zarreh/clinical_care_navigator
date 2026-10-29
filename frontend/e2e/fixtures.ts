// Shared fixtures for the Playwright smoke tests. The backend is fully mocked
// at the network layer (docs/PLAN.md §7): no live LLM or Python process is
// needed, so a screenshot can never silently drift from what the smoke test
// proves the UI does. Event payloads mirror the real node outputs
// (navigator.graph.nodes) so the timeline details render as they do live.

import type { Page } from "@playwright/test";

export const MEDLINEPLUS_URL = "https://medlineplus.gov/lab-tests/hemoglobin-a1c/";
export const STATPEARLS_URL = "https://www.ncbi.nlm.nih.gov/books/NBK470284/";
export const API = "http://localhost:8000";

export const FULL_RECORD_ID = "patient-full-record";
export const CRITICAL_ID = "patient-critical";
export const BASIC_ID = "patient-basic";

const history = (labs: number, analytes: number, medications: number, conditions: number) => ({
  labs,
  analytes,
  medications,
  conditions,
  encounters: 120,
  notes: 6,
});

export const PERSONAS = [
  {
    patient_id: FULL_RECORD_ID,
    role: "full-record",
    name: "Margaret Ellison",
    age: 82,
    gender: "F",
    language: "en",
    literacy: "intermediate",
    headline: "A full record",
    blurb: "The richest history in the data: many labs, medications and conditions to ask about.",
    history: history(7647, 58, 1113, 273),
  },
  {
    patient_id: CRITICAL_ID,
    role: "critical-potassium",
    name: "Daniel Whitaker",
    age: 45,
    gender: "M",
    language: "en",
    literacy: "basic",
    headline: "A hidden critical value",
    blurb: "Their record holds a critical potassium. Ask an ordinary lab question and watch post-flight override the draft.",
    history: history(143, 25, 36, 35),
  },
  {
    patient_id: BASIC_ID,
    role: "basic-literacy",
    name: "Rosa Delgado",
    age: 70,
    gender: "F",
    language: "es",
    literacy: "basic",
    headline: "Basic health literacy",
    blurb: "Answers are written at an easier reading level, and the measured grade is shown.",
    history: history(2234, 72, 95, 110),
  },
];

const CLAIMS = [
  { id: "c1", text: "Your most recent HbA1c was 7.2%.", kind: "clinical", evidence_refs: ["call_labs_1"] },
  {
    id: "c2",
    text: "You can read more about the HbA1c test on MedlinePlus.",
    kind: "navigational",
    evidence_refs: [],
  },
];

export const ANSWERED_PAYLOAD = {
  body:
    "Your most recent HbA1c was 7.2%, which is outside the reference range your " +
    "lab reported (4.0-5.6%). This test reflects your average blood sugar over " +
    "the past few months. Your care team can tell you what it means for you.",
  claims: CLAIMS,
  citations: [
    { claim_id: "c1", tool_call_id: "call_labs_1", title: "Your own lab record" },
    { claim_id: "c2", url: MEDLINEPLUS_URL, title: "MedlinePlus: Hemoglobin A1C" },
  ],
  reading_level_target: 6.0,
  reading_level_measured: 5.8,
  autonomy_level: "L2_balanced",
  disposition: "answered",
  pending_review: false,
};

export const HELD_PAYLOAD = {
  ...ANSWERED_PAYLOAD,
  body:
    "Your most recent HbA1c was 7.2%. You should schedule an appointment to " +
    "start a new diabetes medication.",
  disposition: "pending_review",
  pending_review: true,
};

export const OVERRIDE_PAYLOAD = {
  body:
    "One of your recent results — Potassium at 6.9 mmol/L — is above the critical-high " +
    "level (6.0 mmol/L) at which published guidance advises prompt medical attention. " +
    "Please contact your care team or seek emergency care now rather than waiting.",
  claims: [],
  citations: [],
  reading_level_target: 0,
  reading_level_measured: null,
  autonomy_level: "L2_balanced",
  disposition: "templated",
  pending_review: false,
};

export const EMERGENCY_PAYLOAD = {
  ...OVERRIDE_PAYLOAD,
  body: "What you describe can be a sign of a medical emergency. Call 911 or your local emergency number now.",
};

const PREFLIGHT_ALLOW = [
  ["intake", { literacy_level: "basic", language: "en" }],
  ["contextualize", {}],
  ["detect_language", { question_language: "en" }],
  ["screen_rules", { rule_matches: [] }],
  [
    "classify_intent",
    { intent: { question_class: "lab_education", red_flags: [], confidence: 0.92, rationale_span: "A1c" } },
  ],
  [
    "resolve_policy",
    {
      policy_decision: {
        action: "allow",
        band: "inform",
        rule_matches: [],
        layer_agreement: true,
        tool_scope: { allowed_tool_names: ["get_labs"], row_cap: 25 },
        autonomy_level: "L2_balanced",
      },
    },
  ],
  [
    "investigate",
    {
      evidence: [{ tool_call_id: "call_labs_1", tool_name: "get_labs" }],
      security_events: [],
      tool_call_count: 1,
    },
  ],
  ["draft_answer", { draft: ANSWERED_PAYLOAD }],
  ["extract_claims", { claims: CLAIMS }],
] as const;

const SUPPORTED = [
  { claim_id: "c1", supported: true, evidence_ref: "call_labs_1", reason: "resolves to a get_labs result" },
  { claim_id: "c2", supported: true, evidence_ref: null, reason: "navigational claim, exempt from citation" },
];

type Ev = readonly [string, unknown];

export function sseBody(events: readonly Ev[], finalPayload: { status: string; answer: unknown }): string {
  const lines = events.map(([node, output]) => `data: ${JSON.stringify({ node, output })}\n\n`);
  lines.push(`data: ${JSON.stringify({ node: "__end__", output: finalPayload })}\n\n`);
  return lines.join("");
}

function conversation(id: string, question: string, status: string, answer: unknown, cost = 0.0021) {
  return {
    id,
    conversation_id: id,
    turn: 0,
    question,
    patient_id: FULL_RECORD_ID,
    status,
    created_at: "2026-08-25T00:00:00Z",
    updated_at: "2026-08-25T00:00:18Z",
    answer_kind: status,
    answer,
    error: null,
    total_cost_usd: cost,
    costs:
      cost > 0
        ? [{ node: "draft_answer", model: "gpt-4o-mini", prompt_tokens: 800, completion_tokens: 120, cost_usd: cost }]
        : [],
  };
}

export type RunFixture = { id: string; question: string; sse: string; conversation: unknown };

export const ANSWERED: RunFixture = {
  id: "run-success",
  question: "What is an A1c test?",
  sse: sseBody(
    [...PREFLIGHT_ALLOW, ["post_flight", { post_flight: { disposition: "publish", trigger: "none", claim_analyses: SUPPORTED, citation_coverage: 1 } }], ["publish", { published: ANSWERED_PAYLOAD }]],
    { status: "answered", answer: ANSWERED_PAYLOAD }
  ),
  conversation: conversation("run-success", "What is an A1c test?", "answered", ANSWERED_PAYLOAD),
};

/** A follow-up ("What about the one before that?") that was rewritten into a standalone
 * question. Its thread has two turns: ANSWERED, then this. */
export const FOLLOW_UP_QUESTION = "What about the one before that?";
export const REWRITE = "What was my previous A1c result?";
const FOLLOW_UP_PAYLOAD = {
  ...ANSWERED_PAYLOAD,
  body: "Your previous HbA1c was 6.8%. It was recorded about a year earlier.",
};
export const FOLLOW_UP: RunFixture = {
  id: "run-follow",
  question: FOLLOW_UP_QUESTION,
  sse: sseBody(
    [
      PREFLIGHT_ALLOW[0],
      ["contextualize", { question: REWRITE, original_question: FOLLOW_UP_QUESTION }],
      ...PREFLIGHT_ALLOW.slice(2),
      ["post_flight", { post_flight: { disposition: "publish", trigger: "none", claim_analyses: SUPPORTED, citation_coverage: 1 } }],
      ["publish", { published: FOLLOW_UP_PAYLOAD }],
    ],
    { status: "answered", answer: FOLLOW_UP_PAYLOAD }
  ),
  conversation: {
    ...conversation("run-follow", FOLLOW_UP_QUESTION, "answered", FOLLOW_UP_PAYLOAD),
    conversation_id: "run-success",
    turn: 1,
  },
};

export const TWO_TURN_THREAD = {
  conversation_id: "run-success",
  patient_id: FULL_RECORD_ID,
  turns: [
    { run_id: "run-success", turn: 0, question: "What is an A1c test?", status: "answered" },
    { run_id: "run-follow", turn: 1, question: FOLLOW_UP_QUESTION, status: "answered" },
  ],
};

export const HELD: RunFixture = {
  id: "run-held",
  question: "Do I need to change my treatment?",
  sse: sseBody(
    [
      ...PREFLIGHT_ALLOW,
      [
        "post_flight",
        {
          post_flight: {
            disposition: "review",
            trigger: "scope_judge",
            override_action: "clinician_review",
            claim_analyses: SUPPORTED,
            citation_coverage: 1,
            scope_judgement: { directs_clinical_action: true },
          },
        },
      ],
      ["enqueue_review", {}],
    ],
    { status: "pending_review", answer: HELD_PAYLOAD }
  ),
  conversation: conversation("run-held", "Do I need to change my treatment?", "pending_review", HELD_PAYLOAD),
};

export const OVERRIDE: RunFixture = {
  id: "run-override",
  question: "What does my potassium of 6.9 mean?",
  sse: sseBody(
    [
      ...PREFLIGHT_ALLOW,
      [
        "post_flight",
        {
          post_flight: {
            disposition: "escalate",
            trigger: "critical_value",
            override_action: "direct_to_emergency_care",
            critical_findings: [
              {
                analyte: "Potassium",
                value: 6.9,
                unit: "mmol/L",
                band: "critical_high",
                threshold: 6.0,
                action: "direct_to_emergency_care",
                source_name: "StatPearls: Hyperkalemia",
                source_url: STATPEARLS_URL,
              },
            ],
            claim_analyses: SUPPORTED,
            citation_coverage: 1,
          },
        },
      ],
      ["template_response", { draft: OVERRIDE_PAYLOAD, published: OVERRIDE_PAYLOAD }],
    ],
    { status: "templated", answer: OVERRIDE_PAYLOAD }
  ),
  conversation: {
    ...conversation("run-override", "What does my potassium of 6.9 mean?", "templated", OVERRIDE_PAYLOAD),
    patient_id: CRITICAL_ID,
  },
};

export const EMERGENCY: RunFixture = {
  id: "run-emergency",
  question: "I have crushing chest pain and my left arm is numb.",
  sse: sseBody(
    [
      ["intake", {}],
      ["detect_language", { question_language: "en" }],
      ["screen_rules", { rule_matches: [{ rule_id: "cardiac-chest-pain", matched_span: "crushing chest pain" }] }],
      [
        "classify_intent",
        { intent: { question_class: "red_flag", red_flags: [{ category: "cardiac", span: "chest pain" }], confidence: 0.97 } },
      ],
      [
        "resolve_policy",
        {
          policy_decision: {
            action: "direct_to_emergency_care",
            band: "escalate",
            rule_matches: [],
            layer_agreement: true,
            autonomy_level: "L2_balanced",
          },
        },
      ],
      ["template_response", { draft: EMERGENCY_PAYLOAD }],
    ],
    { status: "answered", answer: EMERGENCY_PAYLOAD }
  ),
  conversation: conversation(
    "run-emergency",
    "I have crushing chest pain and my left arm is numb.",
    "answered",
    EMERGENCY_PAYLOAD,
    0.0003
  ),
};

export const PENDING_REVIEW = {
  id: "review-1",
  run_id: "run-held",
  patient_id: FULL_RECORD_ID,
  reason: "scope_judge",
  override_action: "clinician_review",
  body: HELD_PAYLOAD.body,
  status: "pending",
  created_at: "2026-08-25T00:00:05Z",
};

export const ALL_RUNS = [ANSWERED, HELD, OVERRIDE, EMERGENCY];

/** Mocks GET /personas. Every page that shows the picker or a patient label needs it. */
export async function mockPersonas(page: Page, personas: unknown[] = PERSONAS) {
  await page.route(`${API}/personas`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(personas) })
  );
}

/** Mocks GET /conversations/{id} and its SSE stream for each run. */
export async function mockRuns(page: Page, runs: RunFixture[] = ALL_RUNS) {
  for (const run of runs) {
    await page.route(`${API}/conversations/${run.id}/events`, (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: run.sse })
    );
    await page.route(`${API}/conversations/${run.id}`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(run.conversation) })
    );
    // By default a run is a one-turn conversation; follow-up tests override this route.
    await page.route(`${API}/conversations/${run.id}/thread`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation_id: run.id,
          patient_id: (run.conversation as { patient_id: string }).patient_id,
          turns: [{ run_id: run.id, turn: 0, question: run.question, status: (run.conversation as { status: string }).status }],
        }),
      })
    );
  }
}

/** Routes POST /conversations to the fixture whose question matches. Returns a
 * counter so a test can assert how many runs were started. */
export async function mockCreate(
  page: Page,
  runs: RunFixture[] = ALL_RUNS
): Promise<{ count: number; bodies: { question: string; patient_id?: string | null; follow_up_to?: string }[] }> {
  const calls: { count: number; bodies: { question: string; patient_id?: string | null; follow_up_to?: string }[] } = {
    count: 0,
    bodies: [],
  };
  await page.route(`${API}/conversations`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    calls.count += 1;
    const body = route.request().postDataJSON() as { question: string; patient_id?: string | null; follow_up_to?: string };
    calls.bodies.push(body);
    const run = runs.find((r) => r.question === body.question) ?? runs[0];
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: run.id, status: "running" }),
    });
  });
  return calls;
}
