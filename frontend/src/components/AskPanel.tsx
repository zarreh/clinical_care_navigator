"use client";

import { ArrowRight, LoaderCircle, Send, Timer } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { PersonaHelp, PersonaPicker } from "@/components/PersonaPicker";
import { ConversationThread } from "@/components/ConversationThread";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { ApiError, createConversation, type Persona } from "@/lib/api";
import { docsLink } from "@/lib/docs";
import { findPersona } from "@/lib/personas";
import { MAX_QUESTION_LENGTH, SCENARIOS, type ScenarioOutcome } from "@/lib/scenarios";
import { usePersonas } from "@/lib/usePersonas";

const OUTCOME_BADGE: Record<ScenarioOutcome, { label: string; variant: BadgeVariant }> = {
  answered: { label: "Answered", variant: "green" },
  refused: { label: "Refused & routed", variant: "indigo" },
  emergency: { label: "Emergency guidance", variant: "red" },
  escalated: { label: "Safety override", variant: "amber" },
};

/**
 * Nothing runs until the visitor asks: a live run costs model calls and takes
 * tens of seconds, so it starts from a click (an event handler, not an effect,
 * so React's dev double-invocation cannot start it twice). The run id goes in
 * the URL, so a refresh or a shared link replays the same run from the store.
 */
export function AskPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run");
  const { personas, loading: personasLoading, error: personasError } = usePersonas();
  // The chosen patient lives in the URL so a shared link keeps who it was asked as.
  const selected: Persona | undefined = findPersona(personas, searchParams.get("patient")) ?? personas[0];

  const [question, setQuestion] = useState("");
  const [starting, setStarting] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const busy = starting !== null || running;

  useEffect(() => {
    if (runId) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [runId]);

  function link(patientId: string | undefined, run: string | null): string {
    const params = new URLSearchParams();
    if (patientId) params.set("patient", patientId);
    if (run) params.set("run", run);
    const query = params.toString();
    return query ? `${pathname}?${query}` : pathname;
  }

  function choosePersona(patientId: string) {
    router.replace(link(patientId, runId), { scroll: false });
  }

  /** A scenario asks as the persona whose record it needs (the planted critical
   * potassium lives on one patient); free text asks as whoever is selected. */
  async function start(text: string, as?: Persona) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const persona = as ?? selected;
    setStarting(trimmed);
    setStartError(null);
    try {
      const created = await createConversation(trimmed, persona?.patient_id);
      router.replace(link(persona?.patient_id, created.id), { scroll: false });
    } catch (error) {
      setStartError(error instanceof ApiError ? error.message : "Could not start the conversation.");
    } finally {
      setStarting(null);
    }
  }

  return (
    <div className="space-y-6">
      <section aria-labelledby="persona-heading" className="space-y-3">
        <h3 id="persona-heading" className="font-semibold text-slate-900 dark:text-white">
          Who are you asking as?
          <PersonaHelp />
        </h3>
        {personasLoading && (
          <p role="status" className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
            <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> Loading the demo patients…
          </p>
        )}
        {personasError && (
          <Callout variant="warning" role="alert" title="Demo patients unavailable">
            {personasError} Questions will use the server&apos;s default patient.
          </Callout>
        )}
        {personas.length > 0 && (
          <PersonaPicker
            personas={personas}
            selectedId={selected?.patient_id}
            onSelect={choosePersona}
            disabled={busy}
          />
        )}
      </section>

      <ul className="grid gap-4 sm:grid-cols-2" aria-label="Example questions">
        {SCENARIOS.map((scenario) => {
          const badge = OUTCOME_BADGE[scenario.outcome];
          const asPersona = personas.find((p) => p.role === scenario.persona) ?? selected;
          return (
            <li
              key={scenario.id}
              className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-slate-900 dark:text-white">{scenario.title}</h3>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </div>
              <p className="mt-2 text-[15px] italic text-slate-700 dark:text-slate-200">“{scenario.question}”</p>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                {scenario.expect}
              </p>
              {asPersona && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Asks as: <span className="font-medium text-slate-700 dark:text-slate-200">{asPersona.name}</span>{" "}
                  ({asPersona.headline.toLowerCase()})
                </p>
              )}
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Deciding call: <span className="font-medium text-indigo-700 dark:text-indigo-300">{scenario.decidedBy}</span>
              </p>
              <div className="mt-4 flex items-center justify-between gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void start(scenario.question, asPersona)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {starting === scenario.question ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
                  ) : (
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  )}
                  Run this question
                </button>
                <a
                  href={docsLink(scenario.doc)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-medium text-sky-700 hover:underline dark:text-sky-400"
                >
                  Why?
                </a>
              </div>
            </li>
          );
        })}
      </ul>

      <form
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        onSubmit={(event) => {
          event.preventDefault();
          void start(question);
        }}
      >
        <label htmlFor="question" className="font-semibold text-slate-900 dark:text-white">
          Or ask your own question
        </label>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          About {selected ? <strong>{selected.name}&apos;s</strong> : "the selected patient\'s"} labs,
          medications, conditions or visits. Try to break it, too: ask for someone else&apos;s record
          or for a diagnosis.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            id="question"
            type="text"
            value={question}
            maxLength={MAX_QUESTION_LENGTH}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What medications am I taking?"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length === 0}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {starting === question.trim() ? (
              <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="h-4 w-4" aria-hidden />
            )}
            Ask
          </button>
        </div>
        <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
          <Timer className="h-3.5 w-3.5" aria-hidden />
          A live run calls a real AI model and usually takes 15–40 seconds. Questions stopped at
          pre-flight finish in a second or two.
        </p>
      </form>

      {starting && (
        <p role="status" className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> Starting the conversation…
        </p>
      )}

      {startError && (
        <Callout variant="error" role="alert" title="The run did not start">
          {startError}
        </Callout>
      )}

      <div ref={resultRef} className="scroll-mt-20">
        {runId && (
          <ConversationThread
            runId={runId}
            personas={personas}
            onRunningChange={setRunning}
            onFocus={(id) => router.replace(link(selected?.patient_id, id), { scroll: false })}
            onFollowUp={(id) => router.replace(link(selected?.patient_id, id), { scroll: false })}
            onNewConversation={() => router.replace(link(selected?.patient_id, null), { scroll: false })}
          />
        )}
      </div>
    </div>
  );
}
