import { CircleCheck, CircleX, ListChecks, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { Meter } from "@/components/ui/Meter";
import { GLOSSARY } from "@/lib/glossary";
import { POSTFLIGHT_LABELS, TRIGGER_LABELS, type RunSummary } from "@/lib/run";

const SECURITY_LABELS: Record<string, string> = {
  cross_patient_overwrite: "a lookup aimed at another patient id was pinned back to this patient",
  blocked_unknown_tool: "a call to a tool that does not exist was blocked",
  out_of_scope_tool: "a tool outside this question's allowed set was blocked",
  suspected_indirect_injection: "instructions hidden inside a record were treated as data, not obeyed",
};

/** The post-flight verdict on each claim of the final draft: the evidence the
 * publish decision actually rested on (docs/PLAN.md §5.3). */
export function ClaimsCheck({ summary }: { summary: RunSummary }) {
  const pf = summary.postFlight;
  if (!pf) {
    return (
      <Card aria-label="Claim check">
        <CardTitle icon={<ListChecks className="h-4 w-4" aria-hidden />}>Claim-by-claim check</CardTitle>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
          Not needed: pre-flight settled this question before the AI read the record, so there was
          no draft to check.
        </p>
      </Card>
    );
  }
  const analyses = new Map(pf.claim_analyses.map((a) => [a.claim_id, a]));
  const scope = pf.scope_judgement;
  const scopeFlags = scope
    ? (
        [
          ["diagnoses", "Makes a diagnosis"],
          ["changes_medication", "Changes a medication"],
          ["directs_clinical_action", "Directs clinical action"],
          ["contradicts_record", "Contradicts the record"],
        ] as const
      ).filter(([key]) => scope[key])
    : [];
  const coverage = pf.citation_coverage;
  return (
    <Card aria-label="Claim check">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle icon={<ListChecks className="h-4 w-4" aria-hidden />}>
          Claim-by-claim check
          <InfoTip text={GLOSSARY.claim} />
        </CardTitle>
        <Badge variant={pf.disposition === "publish" ? "green" : pf.disposition === "escalate" ? "red" : "amber"}>
          {POSTFLIGHT_LABELS[pf.disposition] ?? pf.disposition}
        </Badge>
      </div>

      <div className="mt-4 space-y-1">
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
          Citation coverage of clinical claims
          <InfoTip text={GLOSSARY.citationCoverage} />
        </p>
        <Meter
          value={coverage}
          max={1}
          label="Citation coverage"
          display={`${Math.round(coverage * 100)}%`}
          tone={coverage >= 1 ? "green" : "amber"}
        />
      </div>

      {summary.postFlightPasses > 1 && (
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
          Post-flight ran {summary.postFlightPasses} times: an earlier draft had an uncited claim, so
          the AI was sent back to the record. The table shows the last check.
        </p>
      )}

      {summary.claims.length > 0 ? (
        <ul className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
          {summary.claims.map((claim) => {
            const a = analyses.get(claim.id);
            const ok = a?.supported ?? false;
            return (
              <li key={claim.id} className="flex gap-3 py-2.5">
                {ok ? (
                  <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Supported" />
                ) : (
                  <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-red-600" aria-label="Not supported" />
                )}
                <div className="min-w-0">
                  <p className="text-sm text-slate-800 dark:text-slate-100">{claim.text}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <Badge variant={claim.kind === "clinical" ? "sky" : "slate"}>{claim.kind}</Badge>
                    <span>{a?.reason ?? "not analysed"}</span>
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-slate-500">The draft contained no claims.</p>
      )}

      {pf.trigger !== "none" && (
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
          Deciding signal: <span className="font-medium">{TRIGGER_LABELS[pf.trigger] ?? pf.trigger}</span>
          {pf.trigger === "critical_value" && <InfoTip text={GLOSSARY.criticalValue} />}
        </p>
      )}

      {scopeFlags.length > 0 && (
        <Callout variant="warning" className="mt-4" title="The AI judge flagged the draft">
          {scopeFlags.map(([, label]) => label).join(", ")}. A patient assistant may explain the
          record but must not do this, so the draft was not published on its own.
        </Callout>
      )}

      {summary.securityEvents.length > 0 && (
        <Callout variant="warning" className="mt-4" title="Tool scoping stepped in">
          <span className="inline-flex items-start gap-1">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>
              {[...new Set(summary.securityEvents.map((e) => SECURITY_LABELS[e.kind] ?? e.kind.replace(/_/g, " ")))]
                .join("; ")
                .replace(/^./, (c) => c.toUpperCase())}
              . The AI can only ever read this patient&apos;s own record.
            </span>
          </span>
        </Callout>
      )}
    </Card>
  );
}
