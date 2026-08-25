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
