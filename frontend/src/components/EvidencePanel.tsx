import { ExternalLink, FileText } from "lucide-react";

import { Badge, DispositionBadge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { Meter } from "@/components/ui/Meter";
import { GLOSSARY } from "@/lib/glossary";
import type { PatientAnswer } from "@/lib/schemas";

const AUTONOMY_LABELS: Record<string, string> = {
  L1_conservative: "Conservative",
  L2_balanced: "Balanced",
  L3_permissive: "Permissive",
};

/** What the patient actually reads, with its sources and reading level. */
export function EvidencePanel({ answer }: { answer: PatientAnswer }) {
  // Several claims usually cite the same lookup; list each source once.
  const seen = new Set<string>();
  const citations = answer.citations.filter((c) => {
    const key = c.url ?? c.tool_call_id ?? c.title ?? c.claim_id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const hasReadingLevel = answer.reading_level_target > 0;
  const measured = answer.reading_level_measured;
  return (
    <Card aria-label="Answer">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle icon={<FileText className="h-4 w-4" aria-hidden />}>What the patient sees</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <DispositionBadge disposition={answer.disposition} />
          <Badge variant="indigo">
            Autonomy: {AUTONOMY_LABELS[answer.autonomy_level] ?? answer.autonomy_level}
          </Badge>
          <InfoTip text={GLOSSARY.autonomy} />
        </div>
      </div>

      {answer.disposition === "pending_review" && (
        <Callout variant="warning" role="status" className="mt-4">
          This answer was held for a clinician to review before it is shown as answered. You are
          seeing the draft, clearly labelled as pending. It has not been approved.
        </Callout>
      )}

      <p className="mt-4 whitespace-pre-line text-[15px] leading-relaxed text-slate-800 dark:text-slate-100">
        {answer.body}
      </p>

      {hasReadingLevel && (
        <div className="mt-5 space-y-1">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Reading level: target grade {answer.reading_level_target.toFixed(1)}
            {measured != null && <>, measured grade {measured.toFixed(1)}</>}
            <InfoTip text={GLOSSARY.readingLevel} />
          </p>
          {measured != null && (
            <Meter
              value={measured}
              max={Math.max(12, measured)}
              label="Measured reading grade"
              display={`gr ${measured.toFixed(1)}`}
              tone={measured <= answer.reading_level_target + 1 ? "green" : "amber"}
            />
          )}
        </div>
      )}

      {citations.length > 0 && (
        <div className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Sources</h3>
          <ul className="mt-2 space-y-1.5 text-sm">
            {citations.map((citation, i) => (
              <li key={i}>
                {citation.url ? (
                  // A citation nobody can open is not a citation (§6.1): education
                  // sources render as clickable links to the real page.
                  <a
                    className="inline-flex items-center gap-1 text-sky-700 underline-offset-2 hover:underline dark:text-sky-400"
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {citation.title ?? citation.url}
                    <ExternalLink className="h-3 w-3" aria-hidden />
                  </a>
                ) : (
                  <span className="text-slate-700 dark:text-slate-300">
                    {citation.title ?? "From your own record"}
                    {citation.tool_call_id && (
                      <span className="font-mono text-xs text-slate-400"> ({citation.tool_call_id})</span>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
