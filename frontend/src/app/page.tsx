"use client";

import { useState } from "react";
import { RunConsole } from "@/components/RunConsole";

// First paint first (docs/PLAN.md §7): a visitor lands and watches a full
// answer stream node-by-node against a preloaded example, before typing
// anything. The two scenarios below are both triggered by a click — the
// second one demonstrates case 4, a benign question over a critical value that
// post-flight escalates.
const SCENARIOS = {
  example: {
    label: "Ask the example question",
    question: "What do my most recent lab results mean?",
  },
  escalation: {
    label: "Show me an escalation (case 4)",
    question: "Can you remind me what my most recent potassium result was?",
  },
} as const;

type ScenarioKey = keyof typeof SCENARIOS;

export default function Home() {
  const [scenario, setScenario] = useState<ScenarioKey>("example");
  const active = SCENARIOS[scenario];

  return (
    <main className="mx-auto max-w-3xl p-8 font-sans">
      <h1 className="text-2xl font-bold">Clinical Care Navigator</h1>
      <p className="mt-2 text-sm text-neutral-500">
        A patient-facing assistant that answers questions about your own record —
        and is allowed to refuse. Every answer is checked against the record
        before you see it, and streamed node-by-node so you can watch the
        guardrails work. This runs entirely on fully synthetic Synthea data.
      </p>

      <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Example questions">
        {(Object.keys(SCENARIOS) as ScenarioKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setScenario(key)}
            aria-pressed={scenario === key}
            className={`rounded border px-3 py-1.5 text-sm ${
              scenario === key
                ? "border-neutral-900 bg-neutral-900 text-white dark:border-neutral-100 dark:bg-neutral-100 dark:text-neutral-900"
                : "border-neutral-300 text-neutral-700 hover:border-neutral-500 dark:border-neutral-700 dark:text-neutral-300"
            }`}
          >
            {SCENARIOS[key].label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {/* Re-key on the scenario so switching restarts the run from scratch. */}
        <RunConsole key={scenario} question={active.question} />
      </div>
    </main>
  );
}
