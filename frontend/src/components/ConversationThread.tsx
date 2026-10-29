"use client";

import { ArrowRight, LoaderCircle, MessageSquarePlus, Plus, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { RunConsole } from "@/components/RunConsole";
import { DispositionBadge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/Card";
import {
  ApiError,
  createConversation,
  getConversation,
  getThread,
  type ConversationResponse,
  type Persona,
  type ThreadResponse,
  type ThreadTurn,
} from "@/lib/api";
import { findPersona } from "@/lib/personas";
import { PatientAnswerSchema } from "@/lib/schemas";
import { MAX_QUESTION_LENGTH } from "@/lib/scenarios";

const STATUS_LABEL: Record<string, string> = {
  running: "Running",
  failed: "Failed",
  answered: "Answered",
  templated: "Safe templated response",
  pending_review: "Pending clinician review",
};

/**
 * One conversation: every turn in order, the focused turn live (the one in the URL) and
 * the others folded away, then a box to ask a follow-up on the latest answer. A follow-up
 * stays with the same patient, so the box says whose record it is about.
 */
export function ConversationThread({
  runId,
  personas,
  onRunningChange,
  onFocus,
  onFollowUp,
  onNewConversation,
}: {
  runId: string;
  personas: Persona[];
  onRunningChange: (running: boolean) => void;
  onFocus: (runId: string) => void;
  onFollowUp: (newRunId: string) => void;
  onNewConversation: () => void;
}) {
  const [thread, setThread] = useState<ThreadResponse | null>(null);
  const [version, setVersion] = useState(0);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getThread(runId)
      .then((result) => !cancelled && setThread(result))
      .catch(() => !cancelled && setThread(null));
    return () => {
      cancelled = true;
    };
  }, [runId, version]);

  // Stable identity matters: RunConsole re-reports whenever this callback changes, so a
  // new function each render would loop (report -> state change -> render -> report).
  const wasRunning = useRef(false);
  const handleRunning = useCallback(
    (value: boolean) => {
      const finished = wasRunning.current && !value;
      wasRunning.current = value;
      setRunning(value);
      onRunningChange(value);
      // The thread's last status was read when the run started; refresh it once it ends.
      if (finished) setVersion((v) => v + 1);
    },
    [onRunningChange]
  );

  const turns = thread?.turns ?? [];
  const latest = turns.at(-1);
  const patient = findPersona(personas, thread?.patient_id);
  const canFollowUp = !running && latest !== undefined && latest.status !== "running";

  return (
    <div className="space-y-6">
      {turns.length > 1 && (
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
          Conversation · {turns.length} questions
        </p>
      )}

      {(turns.length > 0 ? turns : [{ run_id: runId, turn: 0, question: "", status: "running" }]).map(
        (turn) =>
          turn.run_id === runId ? (
            <RunConsole key={runId} runId={runId} personas={personas} onRunningChange={handleRunning} />
          ) : (
            <PreviousTurn key={turn.run_id} turn={turn} onOpen={() => onFocus(turn.run_id)} />
          )
      )}

      {canFollowUp && latest && (
        <FollowUpBox
          latest={latest}
          patientName={patient?.name}
          onAsked={onFollowUp}
          onNewConversation={onNewConversation}
        />
      )}
    </div>
  );
}

function PreviousTurn({ turn, onOpen }: { turn: ThreadTurn; onOpen: () => void }) {
  const [open, setOpen] = useState(false);
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);

  useEffect(() => {
    if (!open || conversation) return;
    let cancelled = false;
    getConversation(turn.run_id)
      .then((result) => !cancelled && setConversation(result))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [open, conversation, turn.run_id]);

  const parsed = conversation?.answer != null ? PatientAnswerSchema.safeParse(conversation.answer) : null;
  const answer = parsed?.success ? parsed.data : null;

  return (
    <details
      className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm">
        <span className="min-w-0">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Question {turn.turn + 1}
          </span>{" "}
          <span className="font-medium text-slate-900 dark:text-white">{turn.question}</span>
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">{STATUS_LABEL[turn.status] ?? turn.status}</span>
      </summary>
      <div className="space-y-3 border-t border-slate-100 px-5 py-4 dark:border-slate-800">
        {!conversation && (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> Loading…
          </p>
        )}
        {answer && (
          <>
            <DispositionBadge disposition={answer.disposition} />
            <p className="whitespace-pre-line text-[15px] leading-relaxed text-slate-800 dark:text-slate-100">
              {answer.body}
            </p>
          </>
        )}
        {conversation && !answer && (
          <p className="text-sm text-slate-500">
            {conversation.error ?? "This question has no answer to show."}
          </p>
        )}
        <button
          type="button"
          onClick={onOpen}
          className="inline-flex items-center gap-1 text-sm font-medium text-sky-700 hover:underline dark:text-sky-400"
        >
          See how it was checked <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </details>
  );
}

function FollowUpBox({
  latest,
  patientName,
  onAsked,
  onNewConversation,
}: {
  latest: ThreadTurn;
  patientName: string | undefined;
  onAsked: (newRunId: string) => void;
  onNewConversation: () => void;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const question = text.trim();
    if (!question || sending) return;
    setSending(true);
    setError(null);
    try {
      // No patient id: the server keeps the thread's own patient.
      const created = await createConversation(question, undefined, latest.run_id);
      setText("");
      onAsked(created.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send the follow-up.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Card aria-label="Follow-up">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label htmlFor="follow-up" className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
          <MessageSquarePlus className="h-4 w-4 text-sky-600 dark:text-sky-400" aria-hidden />
          Ask a follow-up
        </label>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Still about {patientName ? <strong>{patientName}</strong> : "the same patient"}&apos;s record. You can say
          things like &ldquo;what about the one before that?&rdquo;; it is read in the light of this conversation and then
          checked exactly like any other question.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            id="follow-up"
            type="text"
            value={text}
            maxLength={MAX_QUESTION_LENGTH}
            onChange={(event) => setText(event.target.value)}
            placeholder="e.g. What about the one before that?"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={sending || text.trim().length === 0}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? (
              <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="h-4 w-4" aria-hidden />
            )}
            Ask follow-up
          </button>
        </div>
        {error && (
          <Callout variant="error" role="alert" className="mt-3">
            {error}
          </Callout>
        )}
      </form>
      <button
        type="button"
        onClick={onNewConversation}
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-sky-700 hover:underline dark:text-sky-400"
      >
        <Plus className="h-4 w-4" aria-hidden /> Start a new conversation
      </button>
    </Card>
  );
}
