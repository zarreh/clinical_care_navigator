import {
  ClaimSchema,
  EvidenceRecordSchema,
  IntentAssessmentSchema,
  PolicyDecisionSchema,
  PostFlightResultSchema,
  RuleMatchSchema,
  SecurityEventSchema,
  type Claim,
  type EvidenceRecord,
  type IntentAssessment,
  type PolicyDecision,
  type PostFlightResult,
  type RuleMatch,
  type SecurityEvent,
  type TraceEvent,
} from "./schemas";
import { z } from "zod";

/** The five stages a visitor sees in the stepper, in order. */
export const STAGES = [
  { id: "preflight", label: "Pre-flight screen", owner: "Rules + AI classifier" },
  { id: "investigate", label: "Read your record", owner: "AI, scoped tools" },
  { id: "draft", label: "Draft & split into claims", owner: "AI" },
  { id: "postflight", label: "Post-flight check", owner: "Code + AI judge" },
  { id: "outcome", label: "Outcome", owner: "Code (clinician if held)" },
] as const;

export type StageId = (typeof STAGES)[number]["id"];

export const NODE_STAGE: Record<string, StageId> = {
  intake: "preflight",
  contextualize: "preflight",
  screen_rules: "preflight",
  classify_intent: "preflight",
  detect_language: "preflight",
  resolve_policy: "preflight",
  investigate: "investigate",
  draft_answer: "draft",
  extract_claims: "draft",
  post_flight: "postflight",
  publish: "outcome",
  enqueue_review: "outcome",
  template_response: "outcome",
  budget_exceeded: "outcome",
};

// Node filename == node name == span name (docs/HARVEST.md #9).
export const NODE_LABELS: Record<string, string> = {
  intake: "Reading your question",
  contextualize: "Reading your follow-up in context",
  screen_rules: "Screening for red-flag safety rules",
  classify_intent: "Understanding what you are asking",
  detect_language: "Checking the language of your question",
  resolve_policy: "Deciding what the assistant may do",
  investigate: "Looking things up in your own record",
  draft_answer: "Drafting an answer",
  extract_claims: "Breaking the draft into checkable claims",
  post_flight: "Checking every claim against your record",
  publish: "Publishing the answer",
  enqueue_review: "Holding the answer for clinician review",
  template_response: "Replacing the draft with a safe, pre-written reply",
  budget_exceeded: "Stopped by the cost and time budget",
};

export type RunSummary = {
  /** Set when a follow-up was rewritten into a standalone question. */
  rewrite?: { from: string; to: string };
  intent?: IntentAssessment;
  ruleMatches: RuleMatch[];
  language?: string;
  policy?: PolicyDecision;
  evidence: EvidenceRecord[];
  securityEvents: SecurityEvent[];
  toolCallCount: number;
  claims: Claim[];
  postFlight?: PostFlightResult;
  postFlightPasses: number;
  terminalNode?: string;
  reachedStages: Set<StageId>;
  currentStage?: StageId;
};

function field<T>(output: unknown, key: string, schema: z.ZodType<T>): T | undefined {
  if (output === null || typeof output !== "object" || !(key in output)) return undefined;
  const parsed = schema.safeParse((output as Record<string, unknown>)[key]);
  return parsed.success ? parsed.data : undefined;
}

export function summarizeRun(events: TraceEvent[]): RunSummary {
  const summary: RunSummary = {
    ruleMatches: [],
    evidence: [],
    securityEvents: [],
    toolCallCount: 0,
    claims: [],
    postFlightPasses: 0,
    reachedStages: new Set(),
  };
  for (const { node, output } of events) {
    const stage = NODE_STAGE[node];
    if (stage) {
      summary.reachedStages.add(stage);
      summary.currentStage = stage;
    }
    switch (node) {
      case "contextualize": {
        const to = field(output, "question", z.string());
        const from = field(output, "original_question", z.string());
        if (to && from) summary.rewrite = { from, to };
        break;
      }
      case "screen_rules":
        summary.ruleMatches = field(output, "rule_matches", z.array(RuleMatchSchema)) ?? [];
        break;
      case "classify_intent":
        summary.intent = field(output, "intent", IntentAssessmentSchema);
        break;
      case "detect_language":
        summary.language = field(output, "question_language", z.string());
        break;
      case "resolve_policy":
        summary.policy = field(output, "policy_decision", PolicyDecisionSchema);
        break;
      case "investigate":
        // Evidence and security events are cumulative in state, so the latest wins.
        summary.evidence = field(output, "evidence", z.array(EvidenceRecordSchema)) ?? summary.evidence;
        summary.securityEvents =
          field(output, "security_events", z.array(SecurityEventSchema)) ?? summary.securityEvents;
        summary.toolCallCount = field(output, "tool_call_count", z.number()) ?? summary.toolCallCount;
        break;
      case "extract_claims":
        summary.claims = field(output, "claims", z.array(ClaimSchema)) ?? summary.claims;
        break;
      case "post_flight":
        summary.postFlight = field(output, "post_flight", PostFlightResultSchema) ?? summary.postFlight;
        summary.postFlightPasses += 1;
        break;
      case "publish":
      case "enqueue_review":
      case "template_response":
      case "budget_exceeded":
        summary.terminalNode = node;
        break;
    }
  }
  return summary;
}

/** One short line describing what a node concluded, from its own output. */
export function nodeDetail(event: TraceEvent): string | null {
  const { node, output } = event;
  switch (node) {
    case "contextualize": {
      const to = field(output, "question", z.string());
      return to ? `Understood as: “${to}”` : "A first question, or already clear on its own: no rewrite needed";
    }
    case "screen_rules": {
      const matches = field(output, "rule_matches", z.array(RuleMatchSchema)) ?? [];
      const live = matches.filter((m) => !m.negated && !m.attributed);
      if (live.length === 0) return "No red-flag rule matched";
      return `Matched ${live.map((m) => `“${m.matched_span}”`).join(", ")}`;
    }
    case "classify_intent": {
      const intent = field(output, "intent", IntentAssessmentSchema);
      if (!intent) return null;
      const flags = intent.red_flags.length ? ` · red flag: ${intent.red_flags.map((f) => f.category).join(", ")}` : "";
      return `${humanize(intent.question_class)} (${Math.round(intent.confidence * 100)}% confident)${flags}`;
    }
    case "detect_language": {
      const lang = field(output, "question_language", z.string());
      return lang ? `Language: ${lang}` : null;
    }
    case "resolve_policy": {
      const policy = field(output, "policy_decision", PolicyDecisionSchema);
      if (!policy) return null;
      return `${ACTION_LABELS[policy.action] ?? humanize(policy.action)} · band: ${policy.band}`;
    }
    case "investigate": {
      const evidence = field(output, "evidence", z.array(EvidenceRecordSchema)) ?? [];
      const count = field(output, "tool_call_count", z.number());
      if (count === undefined) return null;
      const names = [...new Set(evidence.map((e) => e.tool_name))];
      return `${count} tool call${count === 1 ? "" : "s"} so far${names.length ? `: ${names.join(", ")}` : ""}`;
    }
    case "extract_claims": {
      const claims = field(output, "claims", z.array(ClaimSchema)) ?? [];
      const clinical = claims.filter((c) => c.kind === "clinical").length;
      return `${claims.length} claim${claims.length === 1 ? "" : "s"} (${clinical} clinical)`;
    }
    case "post_flight": {
      const pf = field(output, "post_flight", PostFlightResultSchema);
      if (!pf) return null;
      return `${POSTFLIGHT_LABELS[pf.disposition] ?? pf.disposition}${pf.trigger !== "none" ? ` · reason: ${TRIGGER_LABELS[pf.trigger] ?? pf.trigger}` : ""}`;
    }
    default:
      return null;
  }
}

export function humanize(value: string): string {
  const s = value.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const ACTION_LABELS: Record<string, string> = {
  allow: "Allowed to answer",
  clinician_review: "Needs a clinician",
  out_of_scope: "Out of scope",
  direct_to_emergency_care: "Emergency: direct to care",
  crisis: "Crisis support",
};

export const POSTFLIGHT_LABELS: Record<string, string> = {
  publish: "Passed, publish",
  loop: "Missing evidence, look again",
  escalate: "Override with a safety message",
  review: "Hold for a clinician",
};

export const TRIGGER_LABELS: Record<string, string> = {
  critical_value: "critical lab value",
  citation_coverage: "uncited clinical claim",
  scope_judge: "the scope check flagged the draft",
};

/** Deterministic, hydration-safe timestamp. */
export function formatTimestamp(iso: string): string {
  return `${iso.slice(0, 16).replace("T", " ")} UTC`;
}
