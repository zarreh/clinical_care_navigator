import type { TraceEvent } from "@/lib/schemas";

// Node filename == node name == span name (docs/HARVEST.md #9). These labels
// are the patient-facing names for each node in navigator.graph.
const NODE_LABELS: Record<string, string> = {
  intake: "Reading your question",
  screen_rules: "Screening for red-flag safety rules",
  classify_intent: "Understanding what you are asking",
  resolve_policy: "Resolving the applicable policy",
  investigate: "Looking up your own record",
  draft_answer: "Drafting an answer",
  extract_claims: "Breaking the draft into checkable claims",
  post_flight: "Checking every claim against your record",
  publish: "Publishing the answer",
  enqueue_review: "Holding the answer for clinician review",
  template_response: "Returning a safe templated response",
  budget_exceeded: "Stopped by the cost guardrail",
};

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  // __end__ is a stream-termination marker, not a graph step.
  const steps = events.filter((event) => event.node !== "__end__");
  if (steps.length === 0) {
    return <p className="text-sm text-neutral-500">Waiting for the first step…</p>;
  }
  return (
    <ol className="space-y-2" aria-label="Trace">
      {steps.map((event, i) => (
        <li
          key={i}
          className="flex items-baseline gap-3 rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800"
        >
          <span className="font-mono text-xs text-neutral-400">{i + 1}</span>
          <div>
            <div className="font-semibold">{NODE_LABELS[event.node] ?? event.node}</div>
            <div className="font-mono text-xs text-neutral-500">{event.node}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
