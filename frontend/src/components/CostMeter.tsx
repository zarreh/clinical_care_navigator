import { Coins } from "lucide-react";

import { Card, CardTitle } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import type { ConversationResponse } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary";
import { NODE_LABELS } from "@/lib/run";

// Per-node cost accounting (docs/PLAN.md §5.5). An unknown model prices to zero
// rather than inventing a figure, so a demo run can legitimately show $0.
export function CostMeter({ conversation }: { conversation: ConversationResponse }) {
  return (
    <Card aria-label="Cost">
      <div className="flex items-baseline justify-between">
        <CardTitle icon={<Coins className="h-4 w-4" aria-hidden />}>
          Cost for this answer
          <InfoTip text={GLOSSARY.cost} />
        </CardTitle>
        <span className="font-mono text-sm font-semibold text-slate-900 dark:text-white">
          ${conversation.total_cost_usd.toFixed(4)}
        </span>
      </div>
      {conversation.costs.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          No AI model was called for this answer, or the model is unpriced (an unknown model prices
          to zero rather than inventing a figure).
        </p>
      ) : (
        <table className="mt-3 w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th className="pb-1 font-medium">Step</th>
              <th className="pb-1 font-medium">Model</th>
              <th className="pb-1 text-right font-medium">Tokens</th>
              <th className="pb-1 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {conversation.costs.map((entry, i) => (
              <tr key={i} className="text-slate-700 dark:text-slate-300">
                <td className="py-1">{NODE_LABELS[entry.node] ?? entry.node}</td>
                <td className="py-1 font-mono">{entry.model}</td>
                <td className="py-1 text-right tabular-nums">{entry.prompt_tokens + entry.completion_tokens}</td>
                <td className="py-1 text-right tabular-nums">${entry.cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
