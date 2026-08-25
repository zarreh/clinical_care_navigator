import type { ConversationResponse } from "@/lib/api";

// Per-node cost accounting (docs/PLAN.md §5.5). An unknown model prices to zero
// rather than inventing a figure, so a demo run can legitimately show $0.
export function CostMeter({ conversation }: { conversation: ConversationResponse }) {
  return (
    <section
      aria-label="Cost"
      className="space-y-2 rounded border border-neutral-200 p-4 dark:border-neutral-800"
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase text-neutral-500">
          Cost for this answer
        </h3>
        <span className="font-mono text-sm">${conversation.total_cost_usd.toFixed(4)}</span>
      </div>
      {conversation.costs.length === 0 ? (
        <p className="text-xs text-neutral-500">
          No LLM cost recorded for this run — an unknown model prices to zero
          rather than inventing a figure.
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-neutral-500">
              <th className="font-normal">Node</th>
              <th className="font-normal">Model</th>
              <th className="font-normal">Tokens</th>
              <th className="font-normal">Cost</th>
            </tr>
          </thead>
          <tbody>
            {conversation.costs.map((entry, i) => (
              <tr key={i}>
                <td className="font-mono">{entry.node}</td>
                <td>{entry.model}</td>
                <td>{entry.prompt_tokens + entry.completion_tokens}</td>
                <td>${entry.cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
