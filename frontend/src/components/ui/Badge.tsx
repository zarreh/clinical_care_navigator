import type { ReactNode } from "react";

const VARIANTS = {
  red: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950 dark:text-red-300 dark:ring-red-400/30",
  amber:
    "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-400/30",
  sky: "bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-950 dark:text-sky-300 dark:ring-sky-400/30",
  indigo:
    "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-400/30",
  green:
    "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-400/30",
  slate:
    "bg-slate-100 text-slate-700 ring-slate-500/20 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-400/30",
} as const;

export type BadgeVariant = keyof typeof VARIANTS;

export function Badge({ children, variant = "slate" }: { children: ReactNode; variant?: BadgeVariant }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${VARIANTS[variant]}`}
    >
      {children}
    </span>
  );
}

// Pending review is labelled as pending, never as approved (docs/PLAN.md §3.7).
const DISPOSITION: Record<string, { label: string; variant: BadgeVariant }> = {
  answered: { label: "Answered", variant: "green" },
  pending_review: { label: "Pending clinician review", variant: "amber" },
  templated: { label: "Safe templated response", variant: "slate" },
};

export function DispositionBadge({ disposition }: { disposition: string }) {
  const d = DISPOSITION[disposition] ?? { label: disposition, variant: "slate" as const };
  return <Badge variant={d.variant}>{d.label}</Badge>;
}

const REASONS: Record<string, { label: string; variant: BadgeVariant }> = {
  critical_value: { label: "Critical lab value", variant: "red" },
  citation_coverage: { label: "Uncited clinical claim", variant: "amber" },
  scope_judge: { label: "Flagged by the scope check", variant: "amber" },
  scope_violation: { label: "Flagged by the scope check", variant: "amber" },
  clinician_review: { label: "Decision needs a clinician", variant: "indigo" },
  recommend: { label: "Decision needs a clinician", variant: "indigo" },
};

export function ReasonBadge({ reason }: { reason: string }) {
  const r = REASONS[reason] ?? { label: reason.replace(/_/g, " "), variant: "slate" as const };
  return <Badge variant={r.variant}>{r.label}</Badge>;
}
