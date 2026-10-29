import Link from "next/link";
import { ArrowRight, CircleCheckBig, ClipboardList, ExternalLink, Hourglass, Siren, ShieldAlert, Ban } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, type CardTone } from "@/components/ui/Card";
import { DispositionBadge } from "@/components/ui/Badge";
import { InfoTip } from "@/components/ui/InfoTip";
import { GLOSSARY } from "@/lib/glossary";
import type { RunSummary } from "@/lib/run";
import type { PatientAnswer } from "@/lib/schemas";

type Outcome = {
  tone: CardTone;
  icon: LucideIcon;
  iconClass: string;
  title: string;
  text: string;
  decidedBy: string;
};

function describe(answer: PatientAnswer, summary: RunSummary): Outcome {
  const pf = summary.postFlight;
  if (answer.disposition === "pending_review") {
    return {
      tone: "amber",
      icon: Hourglass,
      iconClass: "text-amber-600",
      title: "Held for a clinician",
      text: "The AI drafted an answer, but post-flight would not publish it on its own. The draft below is NOT approved. A clinician must approve, edit or decline it first.",
      decidedBy: "Post-flight checks; a clinician makes the final call",
    };
  }
  if (summary.terminalNode === "budget_exceeded") {
    return {
      tone: "amber",
      icon: Hourglass,
      iconClass: "text-amber-600",
      title: "Stopped by the budget",
      text: "The run hit its tool-call or time budget, so it stopped and returned a conservative reply rather than a half-checked answer.",
      decidedBy: "Budget guardrail (code)",
    };
  }
  if (answer.disposition === "templated" && pf && pf.disposition === "escalate") {
    const finding = pf.critical_findings[0];
    return {
      tone: "red",
      icon: ShieldAlert,
      iconClass: "text-red-600",
      title: "Safety override after checking the record",
      text: finding
        ? `The AI drafted an answer, but post-flight found ${finding.analyte} at ${finding.value} ${finding.unit}, beyond the ${finding.band.replace("_", "-")} threshold of ${finding.threshold} ${finding.unit}. The draft was replaced with urgent guidance.`
        : "The AI drafted an answer, but post-flight found something it may not publish, so the draft was replaced with a safe reply.",
      decidedBy: "Post-flight checks (code)",
    };
  }
  if (answer.disposition === "templated") {
    const action = summary.policy?.action;
    if (action === "direct_to_emergency_care" || action === "crisis") {
      return {
        tone: "red",
        icon: Siren,
        iconClass: "text-red-600",
        title: action === "crisis" ? "Crisis support, right away" : "Emergency guidance, right away",
        text: "Pre-flight recognised a possible emergency. The AI never read the record or wrote a draft; a fixed safety message was returned instantly.",
        decidedBy: "Pre-flight red-flag rules + classifier",
      };
    }
    return {
      tone: "default",
      icon: Ban,
      iconClass: "text-indigo-600",
      title:
        action === "clinician_review" ? "A decision for your care team" : "Outside what this assistant may do",
      text: "Pre-flight decided this is not something the assistant may answer, so it stopped before the AI read the record and returned a pre-written reply that routes you to the right person.",
      decidedBy: "Pre-flight policy (rules)",
    };
  }
  return {
    tone: "emerald",
    icon: CircleCheckBig,
    iconClass: "text-emerald-600",
    title: "Published to you",
    text:
      summary.postFlightPasses > 1
        ? "The first draft had a claim without evidence, so the AI went back to the record. The second draft passed every check and code published it."
        : "Every clinical claim rested on evidence actually retrieved from the record, so code published the AI's draft.",
    decidedBy: "Post-flight checks (code)",
  };
}

export function OutcomeCard({ answer, summary }: { answer: PatientAnswer; summary: RunSummary }) {
  const o = describe(answer, summary);
  const finding = summary.postFlight?.critical_findings[0];
  return (
    <Card tone={o.tone} aria-label="Outcome">
      <div className="flex items-start gap-3">
        <o.icon className={`mt-0.5 h-6 w-6 shrink-0 ${o.iconClass}`} aria-hidden />
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{o.title}</h2>
            <DispositionBadge disposition={answer.disposition} />
          </div>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{o.text}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Decided by: <span className="font-medium text-indigo-700 dark:text-indigo-300">{o.decidedBy}</span>
          </p>
          {finding?.source_url && (
            <a
              href={finding.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400"
            >
              Threshold source: {finding.source_name ?? finding.source_url}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          )}
          {answer.disposition === "pending_review" && (
            <Link
              href="/reviews"
              className="inline-flex items-center gap-1 text-sm font-medium text-amber-800 hover:underline dark:text-amber-300"
            >
              <ClipboardList className="h-4 w-4" aria-hidden /> Open the clinician review queue
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          )}
          {answer.disposition === "pending_review" && (
            <p className="text-xs text-slate-500">
              What “held” means
              <InfoTip text={GLOSSARY.pendingReview} />
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
