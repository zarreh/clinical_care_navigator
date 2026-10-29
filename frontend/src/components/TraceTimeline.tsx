import { LoaderCircle } from "lucide-react";

import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import { NODE_LABELS, NODE_STAGE, nodeDetail } from "@/lib/run";
import type { TraceEvent } from "@/lib/schemas";

const STAGE_DOT: Record<string, string> = {
  preflight: "bg-indigo-500",
  investigate: "bg-sky-500",
  draft: "bg-sky-500",
  postflight: "bg-indigo-500",
  outcome: "bg-emerald-500",
};

/** Every graph step as it finished, human label first and the raw node name
 * (== span name in traces, docs/HARVEST.md #9) beneath it. */
export function TraceTimeline({ events, live }: { events: TraceEvent[]; live: boolean }) {
  const steps = events.filter((event) => event.node !== "__end__");
  return (
    <Card aria-label="Trace">
      <CardTitle>
        Step by step
        <InfoTip text="Each row is one step of the run, in the order it finished. Indigo steps are checks and rules, blue steps involve the AI, green is the final outcome." />
      </CardTitle>
      {steps.length === 0 && !live ? (
        <p className="mt-3 text-sm text-slate-500">No steps were recorded.</p>
      ) : (
        <ol className="relative mt-4 space-y-4 border-l border-slate-200 pl-5 dark:border-slate-800">
          {steps.map((event, i) => {
            const detail = nodeDetail(event);
            return (
              <li key={i} className="relative">
                <span
                  className={`absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-white dark:ring-slate-900 ${STAGE_DOT[NODE_STAGE[event.node] ?? ""] ?? "bg-slate-400"}`}
                  aria-hidden
                />
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                  {NODE_LABELS[event.node] ?? event.node}
                </p>
                {detail && <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">{detail}</p>}
                <p className="font-mono text-[11px] text-slate-400">{event.node}</p>
              </li>
            );
          })}
          {live && (
            <li className="relative" role="status">
              <span className="absolute -left-[27px] top-1 flex h-3 w-3 items-center justify-center" aria-hidden>
                <span className="absolute h-3 w-3 animate-ping rounded-full bg-sky-400 opacity-60" />
                <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
              </span>
              <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden />
                {steps.length === 0 ? "Waiting for the first step…" : "Working on the next step…"}
              </p>
            </li>
          )}
        </ol>
      )}
    </Card>
  );
}
