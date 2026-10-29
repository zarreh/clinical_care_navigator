import { Check, CircleX, LoaderCircle, Minus } from "lucide-react";

import { STAGES, type RunSummary } from "@/lib/run";

type StepState = "done" | "active" | "pending" | "skipped" | "error";

const DOT: Record<StepState, string> = {
  done: "bg-sky-600 text-white",
  active: "bg-white text-sky-600 ring-2 ring-sky-600 dark:bg-slate-900",
  pending: "bg-slate-200 text-slate-400 dark:bg-slate-800 dark:text-slate-500",
  skipped: "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500",
  error: "bg-red-600 text-white",
};

/** The five stages of a run. A stage the run never needed (a pre-flight refusal
 * skips the AI entirely) is shown as skipped, which is itself the point. */
export function RunStepper({
  summary,
  finished,
  failed,
}: {
  summary: RunSummary;
  finished: boolean;
  failed: boolean;
}) {
  const states: StepState[] = STAGES.map((stage) => {
    const reached = summary.reachedStages.has(stage.id);
    const current = summary.currentStage === stage.id;
    if (current && failed) return "error";
    if (current && !finished && stage.id !== "outcome") return "active";
    if (reached) return "done";
    if (finished || (summary.currentStage === "outcome" && !reached)) return "skipped";
    if (!summary.currentStage && stage.id === "preflight" && !failed) return "active";
    return "pending";
  });
  return (
    <ol className="grid grid-cols-5 gap-2" aria-label="Run progress">
      {STAGES.map((stage, i) => {
        const state = states[i];
        return (
          <li key={stage.id} className="flex flex-col items-center text-center" aria-current={state === "active" ? "step" : undefined}>
            <div className="flex w-full items-center">
              <span className={`h-0.5 flex-1 ${i === 0 ? "invisible" : states[i - 1] === "done" || states[i - 1] === "skipped" ? "bg-sky-300 dark:bg-sky-800" : "bg-slate-200 dark:bg-slate-800"}`} />
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${DOT[state]}`}>
                {state === "done" && <Check className="h-4 w-4" aria-hidden />}
                {state === "active" && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />}
                {state === "skipped" && <Minus className="h-4 w-4" aria-hidden />}
                {state === "error" && <CircleX className="h-4 w-4" aria-hidden />}
                {state === "pending" && i + 1}
              </span>
              <span className={`h-0.5 flex-1 ${i === STAGES.length - 1 ? "invisible" : state === "done" || state === "skipped" ? "bg-sky-300 dark:bg-sky-800" : "bg-slate-200 dark:bg-slate-800"}`} />
            </div>
            <span className={`mt-2 text-xs font-medium sm:text-sm ${state === "pending" || state === "skipped" ? "text-slate-400 dark:text-slate-500" : "text-slate-900 dark:text-white"}`}>
              {stage.label}
            </span>
            <span className="hidden text-[11px] text-slate-500 sm:block dark:text-slate-400">
              {state === "skipped" ? "Skipped" : stage.owner}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
