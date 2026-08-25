// Shared fixtures for the Playwright smoke tests. The backend is fully mocked
// at the network layer (docs/PLAN.md §7): no live LLM or Python process is
// needed, so a screenshot can never silently drift from what the smoke test
// proves the UI does.

export const MEDLINEPLUS_URL = "https://medlineplus.gov/lab-tests/hemoglobin-a1c/";

export const ANSWERED_PAYLOAD = {
  body:
    "Your most recent HbA1c was 7.2%, which is outside the reference range your " +
    "lab reported (4.0-5.6%). This test reflects your average blood sugar over " +
    "the past few months. Your care team can tell you what it means for you.",
  claims: [
    {
      id: "c1",
      text: "Your most recent HbA1c was 7.2%.",
      kind: "clinical",
      evidence_refs: ["call_labs_1"],
    },
    {
      id: "c2",
      text: "You can read more about the HbA1c test on MedlinePlus.",
      kind: "navigational",
      evidence_refs: [],
    },
  ],
  citations: [
    { claim_id: "c1", tool_call_id: "call_labs_1", title: "Your own lab record" },
    { claim_id: "c2", url: MEDLINEPLUS_URL, title: "MedlinePlus: Hemoglobin A1C" },
  ],
  reading_level_target: 6.0,
  reading_level_measured: 5.8,
  autonomy_level: "suggest",
  disposition: "answered",
  pending_review: false,
};

export const ESCALATED_PAYLOAD = {
  ...ANSWERED_PAYLOAD,
  body:
    "Your most recent potassium was 6.8 mmol/L, which is outside the reference " +
    "range your lab reported (3.5-5.1 mmol/L). Your care team can discuss this " +
    "result with you.",
  claims: [
    {
      id: "c1",
      text: "Your most recent potassium was 6.8 mmol/L.",
      kind: "clinical",
      evidence_refs: ["call_labs_1"],
    },
  ],
  citations: [{ claim_id: "c1", tool_call_id: "call_labs_1", title: "Your own lab record" }],
  disposition: "pending_review",
  pending_review: true,
};

export const ANSWERED_CONVERSATION = {
  id: "run-success",
  question: "What do my most recent lab results mean?",
  patient_id: "synthetic-patient-1",
  status: "answered",
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:05Z",
  answer_kind: "answered",
  answer: ANSWERED_PAYLOAD,
  error: null,
  total_cost_usd: 0.0021,
  costs: [
    {
      node: "draft_answer",
      model: "gpt-4o-mini",
      prompt_tokens: 800,
      completion_tokens: 120,
      cost_usd: 0.0021,
    },
  ],
};

export const ESCALATED_CONVERSATION = {
  ...ANSWERED_CONVERSATION,
  id: "run-escalation",
  question: "Can you remind me what my most recent potassium result was?",
  status: "pending_review",
  answer_kind: "pending_review",
  answer: ESCALATED_PAYLOAD,
};

export const PENDING_REVIEW = {
  id: "review-1",
  run_id: "run-escalation-abcdef",
  patient_id: "synthetic-patient-1",
  reason: "critical_value",
  override_action: "clinician_review",
  body: ESCALATED_PAYLOAD.body,
  status: "pending",
  created_at: "2026-08-25T00:00:05Z",
};

const ANSWERED_NODES = [
  "intake",
  "screen_rules",
  "classify_intent",
  "resolve_policy",
  "investigate",
  "draft_answer",
  "extract_claims",
  "post_flight",
  "publish",
];

const ESCALATED_NODES = [
  "intake",
  "screen_rules",
  "classify_intent",
  "resolve_policy",
  "investigate",
  "draft_answer",
  "extract_claims",
  "post_flight",
  "enqueue_review",
];

export function sseBody(
  nodes: string[],
  finalPayload: { status: string; answer: unknown }
): string {
  const lines = nodes.map((node) => `data: ${JSON.stringify({ node, output: {} })}\n\n`);
  lines.push(`data: ${JSON.stringify({ node: "__end__", output: finalPayload })}\n\n`);
  return lines.join("");
}

export const ANSWERED_SSE = sseBody(ANSWERED_NODES, {
  status: "answered",
  answer: ANSWERED_PAYLOAD,
});

export const ESCALATED_SSE = sseBody(ESCALATED_NODES, {
  status: "pending_review",
  answer: ESCALATED_PAYLOAD,
});

export const EMPTY_SSE = sseBody(ANSWERED_NODES, { status: "answered", answer: null });
