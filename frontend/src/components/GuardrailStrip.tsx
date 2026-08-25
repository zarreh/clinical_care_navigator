import type { PatientAnswer } from "@/lib/schemas";

// The guardrail sandwich as graph structure (docs/HARVEST.md #1, §3.8): the
// post-flight checks decide whether a draft is published, held, or replaced.
// This strip states which of the three happened, and the claim coverage that
// drove it — a clinical claim must carry a resolvable citation to publish (§5.3).
const OUTCOME: Record<
  PatientAnswer["disposition"],
  { tone: string; text: (cited: number, total: number) => string }
> = {
  answered: {
    tone: "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200",
    text: (cited, total) =>
      `Post-flight passed: ${cited}/${total} clinical claims carry evidence, so the answer was published.`,
  },
  pending_review: {
    tone: "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
    text: (cited, total) =>
      `Post-flight escalated: ${cited}/${total} clinical claims carry evidence — the answer is held for a clinician, never published on faith.`,
  },
  templated: {
    tone: "bg-neutral-100 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-300",
    text: () =>
      "Post-flight replaced the draft with a safe templated response rather than show an unsupported answer.",
  },
};

export function GuardrailStrip({ answer }: { answer: PatientAnswer }) {
  const clinical = answer.claims.filter((claim) => claim.kind === "clinical");
  const cited = clinical.filter((claim) => claim.evidence_refs.length > 0).length;
  const outcome = OUTCOME[answer.disposition];
  return (
    <div role="status" className={`rounded p-2 text-xs ${outcome.tone}`}>
      {outcome.text(cited, clinical.length)}
    </div>
  );
}
