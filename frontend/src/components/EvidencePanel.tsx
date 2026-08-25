import type { Disposition, PatientAnswer } from "@/lib/schemas";

// Pending review is labelled as pending, never as approved (docs/PLAN.md §3.7).
// The badge states only what the record can prove.
const DISPOSITION_STYLES: Record<Disposition, string> = {
  answered: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  pending_review: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  templated: "bg-neutral-200 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200",
};

const DISPOSITION_LABELS: Record<Disposition, string> = {
  answered: "Answered",
  pending_review: "Pending clinician review",
  templated: "Safe templated response",
};

export function EvidencePanel({ answer }: { answer: PatientAnswer }) {
  const clinicalClaims = answer.claims.filter((claim) => claim.kind === "clinical");
  return (
    <section
      aria-label="Answer"
      className="space-y-4 rounded border border-neutral-200 p-4 dark:border-neutral-800"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-1 text-xs font-semibold uppercase ${DISPOSITION_STYLES[answer.disposition]}`}
        >
          {DISPOSITION_LABELS[answer.disposition]}
        </span>
        <span className="rounded border border-neutral-300 px-2 py-0.5 text-xs text-neutral-600 dark:border-neutral-700 dark:text-neutral-300">
          Autonomy: {answer.autonomy_level}
        </span>
      </div>

      {answer.disposition === "pending_review" && (
        <p
          role="status"
          className="rounded bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          This answer was held for a clinician to review before it is shown as
          answered. You are seeing the draft, clearly labelled as pending — it has
          not been approved.
        </p>
      )}

      <p className="whitespace-pre-line text-sm">{answer.body}</p>

      <div className="text-xs text-neutral-500">
        Written for a reading level of grade {answer.reading_level_target.toFixed(1)}
        {answer.reading_level_measured != null && (
          <> — measured at grade {answer.reading_level_measured.toFixed(1)}</>
        )}
        . Your reading-level target is shown so the assistant is adapting{" "}
        <em>with</em> you, not silently.
      </div>

      {answer.citations.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase text-neutral-500">Sources</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {answer.citations.map((citation, i) => (
              <li key={i}>
                {citation.url ? (
                  // A citation nobody can open is not a citation (§6.1): education
                  // sources render as clickable links to the real page.
                  <a className="underline" href={citation.url} target="_blank" rel="noreferrer">
                    {citation.title ?? citation.url}
                  </a>
                ) : (
                  <span>
                    {citation.title ?? "From your own record"}
                    {citation.tool_call_id && (
                      <span className="font-mono text-xs text-neutral-500">
                        {" "}
                        ({citation.tool_call_id})
                      </span>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {clinicalClaims.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase text-neutral-500">
            Clinical claims, each resting on evidence
          </h3>
          <ul className="mt-1 space-y-1 text-sm">
            {clinicalClaims.map((claim) => (
              <li key={claim.id}>
                {claim.text}{" "}
                <span className="font-mono text-xs text-neutral-500">
                  [{claim.evidence_refs.length} ref
                  {claim.evidence_refs.length === 1 ? "" : "s"}]
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
