"use client";

import { LoaderCircle, MessageCircleQuestion, RotateCcw, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ClaimsCheck } from "@/components/ClaimsCheck";
import { CostMeter } from "@/components/CostMeter";
import { EvidencePanel } from "@/components/EvidencePanel";
import { OutcomeCard } from "@/components/OutcomeCard";
import { RunStepper } from "@/components/RunStepper";
import { TraceTimeline } from "@/components/TraceTimeline";
import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/Card";
import {
  ApiError,
  getConversation,
  streamConversationEvents,
  type ConversationResponse,
  type Persona,
} from "@/lib/api";
import { findPersona, personaSummary } from "@/lib/personas";
import { summarizeRun } from "@/lib/run";
import { PatientAnswerSchema, type TraceEvent } from "@/lib/schemas";

type Phase = "loading" | "streaming" | "done" | "timeout" | "error";

function seconds(fromIso: string, toMs: number): number {
  return Math.max(0, Math.round((toMs - Date.parse(fromIso)) / 1000));
}

export function RunConsole({
  runId,
  personas = [],
  onRunningChange,
}: {
  runId: string;
  personas?: Persona[];
  onRunningChange?: (running: boolean) => void;
}) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    let close = () => {};

    async function finish() {
      try {
        const result = await getConversation(runId);
        if (cancelled) return;
        setConversation(result);
        setPhase(result.status === "running" ? "timeout" : "done");
      } catch (error) {
        if (cancelled) return;
        setPhase("error");
        setErrorMessage(error instanceof ApiError ? error.message : "Could not load the finished answer.");
      }
    }

    async function begin() {
      setPhase("loading");
      setEvents([]);
      setErrorMessage(null);
      try {
        const initial = await getConversation(runId);
        if (cancelled) return;
        setConversation(initial);
      } catch (error) {
        if (cancelled) return;
        setPhase("error");
        setErrorMessage(
          error instanceof ApiError && error.status === 404
            ? "This run no longer exists. The server's run history may have been reset. Start a new question above."
            : error instanceof ApiError
              ? error.message
              : "Could not load this run."
        );
        return;
      }
      setPhase("streaming");
      close = streamConversationEvents(runId, {
        onEvent: (event) => {
          if (cancelled || event.node === "__end__") return;
          setEvents((prev) => [...prev, event]);
        },
        onEnd: () => {
          if (!cancelled) void finish();
        },
        onError: () => {
          if (cancelled) return;
          // The stream can drop (rate limit, network) after the run already
          // finished; the stored record is the source of truth either way.
          void (async () => {
            try {
              const result = await getConversation(runId);
              if (cancelled) return;
              setConversation(result);
              if (result.status !== "running") {
                setPhase("done");
                return;
              }
            } catch {
              // fall through to the error state
            }
            if (cancelled) return;
            setPhase("error");
            setErrorMessage(
              "Lost the live connection while the run was still going. Reconnect to pick it up again."
            );
          })();
        },
      });
    }

    void begin();
    return () => {
      cancelled = true;
      close();
    };
  }, [runId, attempt]);

  const live = phase === "loading" || phase === "streaming";

  useEffect(() => {
    onRunningChange?.(live);
  }, [live, onRunningChange]);
  useEffect(() => () => onRunningChange?.(false), [onRunningChange]);

  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [live]);

  const summary = useMemo(() => summarizeRun(events), [events]);
  const parsedAnswer =
    conversation?.answer != null ? PatientAnswerSchema.safeParse(conversation.answer) : null;
  const answer = parsedAnswer?.success ? parsedAnswer.data : null;
  const failed = conversation?.status === "failed";
  const elapsed = conversation
    ? live
      ? seconds(conversation.created_at, now)
      : seconds(conversation.created_at, Date.parse(conversation.updated_at))
    : null;

  return (
    <div className="space-y-6">
      <Card aria-label="Run summary">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <MessageCircleQuestion
              className="mt-0.5 h-5 w-5 shrink-0 text-sky-600 dark:text-sky-400"
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                You asked
              </p>
              <p className="mt-0.5 text-lg font-medium text-slate-900 dark:text-white">
                {conversation?.question ?? "…"}
              </p>
              {summary.rewrite && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Understood as{" "}
                  <span className="font-medium text-slate-700 dark:text-slate-200">“{summary.rewrite.to}”</span>
                </p>
              )}
              {conversation && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Asked as{" "}
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {(() => {
                      const persona = findPersona(personas, conversation.patient_id);
                      return persona ? personaSummary(persona) : `patient ${conversation.patient_id.slice(0, 8)}`;
                    })()}
                  </span>
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {live && (
              <Badge variant="sky">
                <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden /> Running
              </Badge>
            )}
            {phase === "done" && !failed && <Badge variant="green">Finished</Badge>}
            {(failed || phase === "error") && <Badge variant="red">Failed</Badge>}
            {phase === "timeout" && <Badge variant="amber">Still running</Badge>}
            {elapsed !== null && (
              <span className="inline-flex items-center gap-1 text-xs tabular-nums text-slate-500 dark:text-slate-400">
                <Timer className="h-3.5 w-3.5" aria-hidden /> {elapsed}s
              </span>
            )}
          </div>
        </div>
        <div className="mt-5">
          <RunStepper
            summary={summary}
            finished={phase === "done" && !failed}
            failed={failed || phase === "error"}
          />
        </div>
      </Card>

      {phase === "loading" && (
        <p role="status" className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> Connecting to the run…
        </p>
      )}

      {phase === "error" && (
        <Callout variant="error" role="alert" title="Something went wrong">
          <span>{errorMessage}</span>
          {conversation?.status === "running" && (
            <button
              type="button"
              onClick={() => setAttempt((n) => n + 1)}
              className="mt-2 flex items-center gap-1.5 rounded-lg border border-red-300 px-3 py-1 text-sm font-medium hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/40"
            >
              <RotateCcw className="h-4 w-4" aria-hidden /> Reconnect
            </button>
          )}
        </Callout>
      )}

      {phase === "done" && failed && (
        <Callout variant="error" role="alert" title="This run failed">
          <span>
            {conversation?.error ?? "The conversation failed."} Nothing was shown to the patient.
            Try the question again.
          </span>
        </Callout>
      )}

      {phase === "timeout" && (
        <Callout variant="warning" title="Taking longer than expected">
          The run passed its time budget and has not finished. Reload this page in a moment to see
          whether it completed.
        </Callout>
      )}

      {phase === "done" && !failed && !answer && (
        <Callout role="status" title="No answer">
          The conversation finished but produced no answer.
        </Callout>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <TraceTimeline events={events} live={live} />
        </div>
        <div className="space-y-6 lg:col-span-3">
          {live && (
            <Callout title="What happens while you wait">
              Each step on the left appears the moment it finishes. Pre-flight decides whether the
              AI may answer at all. If it may, the AI reads the record and drafts an answer, and
              post-flight checks every claim before anything is shown.
            </Callout>
          )}
          {phase === "done" && answer && (
            <>
              <OutcomeCard answer={answer} summary={summary} />
              <EvidencePanel answer={answer} />
              <ClaimsCheck summary={summary} />
            </>
          )}
          {conversation && phase === "done" && !failed && <CostMeter conversation={conversation} />}
        </div>
      </div>
    </div>
  );
}
