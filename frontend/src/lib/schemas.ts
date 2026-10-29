import { z } from "zod";

/**
 * Mirrors src/navigator/schemas/answer.py. The OpenAPI-generated types
 * (api-types.ts) type `answer` as a bare `Record<string, unknown>` — the
 * PatientAnswer is returned as opaque JSON, not a typed response model, so its
 * Pydantic schema is not in the OpenAPI document. These Zod schemas are the
 * frontend's own source of truth for what is actually inside it, validated at
 * runtime rather than merely cast (docs/PLAN.md §7).
 */

export const ClaimKindSchema = z.enum(["clinical", "navigational"]);

export const ClaimSchema = z.object({
  id: z.string(),
  text: z.string(),
  kind: ClaimKindSchema,
  evidence_refs: z.array(z.string()).default([]),
});

/** A resolvable citation. `url` is present for education sources so the reader
 * can independently review the basis of the output — one of the four FDA CDS
 * device-exclusion criteria (§6.1). A citation nobody can open is not a
 * citation, so the UI only renders `url` citations as links. */
export const CitationSchema = z.object({
  claim_id: z.string(),
  tool_call_id: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
});

export const DispositionSchema = z.enum(["answered", "pending_review", "templated"]);

export const PatientAnswerSchema = z.object({
  body: z.string(),
  claims: z.array(ClaimSchema).default([]),
  citations: z.array(CitationSchema).default([]),
  reading_level_target: z.number(),
  reading_level_measured: z.number().nullable().optional(),
  autonomy_level: z.string(),
  disposition: DispositionSchema.default("answered"),
  pending_review: z.boolean().default(false),
});

export type Claim = z.infer<typeof ClaimSchema>;
export type Citation = z.infer<typeof CitationSchema>;
export type PatientAnswer = z.infer<typeof PatientAnswerSchema>;
export type Disposition = z.infer<typeof DispositionSchema>;

/** One node's SSE event (navigator.api.streaming). */
export const TraceEventSchema = z.object({
  node: z.string(),
  output: z.unknown(),
});
export type TraceEvent = z.infer<typeof TraceEventSchema>;

/** The terminal SSE event's payload (navigator.api.streaming.stream_conversation_events). */
export const TraceEndOutputSchema = z.object({
  status: z.string(),
  answer: z.record(z.string(), z.unknown()).nullable(),
});

// ---------------------------------------------------------------------------
// Per-node event payloads (navigator.graph.nodes). Parsed leniently with
// safeParse: the trace is explanatory, so an unexpected shape degrades to "no
// detail" rather than breaking the page.

export const RedFlagSchema = z.object({ category: z.string(), span: z.string() });

export const IntentAssessmentSchema = z.object({
  question_class: z.string(),
  red_flags: z.array(RedFlagSchema).default([]),
  confidence: z.number(),
  rationale_span: z.string().optional(),
});

export const RuleMatchSchema = z.object({
  rule_id: z.string(),
  matched_span: z.string(),
  negated: z.boolean().default(false),
  attributed: z.boolean().default(false),
});

export const PolicyDecisionSchema = z.object({
  action: z.string(),
  band: z.string(),
  rule_matches: z.array(RuleMatchSchema).default([]),
  layer_agreement: z.boolean(),
  tool_scope: z
    .object({ allowed_tool_names: z.array(z.string()).default([]), row_cap: z.number() })
    .optional(),
  autonomy_level: z.string(),
  template_id: z.string().nullable().optional(),
  language_limitation: z.boolean().default(false),
});

export const EvidenceRecordSchema = z.object({
  tool_call_id: z.string(),
  tool_name: z.string(),
});

export const SecurityEventSchema = z.object({
  kind: z.string(),
  tool_name: z.string(),
  requested: z.string(),
  enforced: z.string(),
});

export const ClaimAnalysisSchema = z.object({
  claim_id: z.string(),
  supported: z.boolean(),
  evidence_ref: z.string().nullable().optional(),
  reason: z.string(),
});

export const CriticalFindingSchema = z.object({
  analyte: z.string(),
  value: z.number(),
  unit: z.string(),
  band: z.string(),
  threshold: z.number(),
  action: z.string(),
  source_name: z.string().nullable().optional(),
  source_url: z.string().nullable().optional(),
});

export const PostFlightResultSchema = z.object({
  disposition: z.string(),
  trigger: z.string().default("none"),
  override_action: z.string().nullable().optional(),
  critical_findings: z.array(CriticalFindingSchema).default([]),
  claim_analyses: z.array(ClaimAnalysisSchema).default([]),
  citation_coverage: z.number().default(1),
  uncited_claim_ids: z.array(z.string()).default([]),
  scope_judgement: z
    .object({
      diagnoses: z.boolean().default(false),
      changes_medication: z.boolean().default(false),
      directs_clinical_action: z.boolean().default(false),
      contradicts_record: z.boolean().default(false),
    })
    .nullable()
    .optional(),
  evidence_pass: z.number().default(0),
});

export type IntentAssessment = z.infer<typeof IntentAssessmentSchema>;
export type RuleMatch = z.infer<typeof RuleMatchSchema>;
export type PolicyDecision = z.infer<typeof PolicyDecisionSchema>;
export type EvidenceRecord = z.infer<typeof EvidenceRecordSchema>;
export type SecurityEvent = z.infer<typeof SecurityEventSchema>;
export type ClaimAnalysis = z.infer<typeof ClaimAnalysisSchema>;
export type CriticalFinding = z.infer<typeof CriticalFindingSchema>;
export type PostFlightResult = z.infer<typeof PostFlightResultSchema>;
