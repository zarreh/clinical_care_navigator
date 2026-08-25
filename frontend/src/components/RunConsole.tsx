"use client";

import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  getConversation,
  streamConversationEvents,
  type ConversationResponse,
} from "@/lib/api";
import { PatientAnswerSchema, type TraceEvent } from "@/lib/schemas";
import { TraceTimeline } from "./TraceTimeline";
import { EvidencePanel } from "./EvidencePanel";
import { GuardrailStrip } from "./GuardrailStrip";
import { CostMeter } from "./CostMeter";

type Phase = "loading" | "streaming" | "success" | "empty" | "error";

export function RunConsole({
  question,
  patientId,
}: {
  question: string;
  patientId?: string;
}) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const cleanupRef = useRef<() => void>(() => {});

  useEffect(() => {
    let cancelled = false;

    async function finish(id: string) {
      try {
        const result = await getConversation(id);
        if (cancelled) return;
        setConversation(result);
        if (result.status === "failed") {
          setPhase("error");
          setErrorMessage(result.error ?? "The conversation failed.");
        } else if (!result.answer) {
          setPhase("empty");
        } else {
          setPhase("success");
        }
      } catch {
        if (!cancelled) {
          setPhase("error");
          setErrorMessage("Could not fetch the finished answer.");
        }
      }
    }

    async function start() {
      setPhase("loading");
      setEvents([]);
      setConversation(null);
      setErrorMessage(null);
      try {
        const created = await createConversation(question, patientId);
        if (cancelled) return;
        setPhase("streaming");
        cleanupRef.current = streamConversationEvents(created.id, {
          onEvent: (event) => {
            if (cancelled) return;
            setEvents((prev) => [...prev, event]);
          },
          onEnd: () => {
            if (cancelled) return;
            void finish(created.id);
          },
          onError: () => {
            if (cancelled) return;
            setPhase("error");
            setErrorMessage("Lost connection to the answer stream.");
          },
        });
      } catch {
        if (!cancelled) {
          setPhase("error");
          setErrorMessage("Could not start the conversation.");
        }
      }
    }

    void start();
    return () => {
      cancelled = true;
      cleanupRef.current();
    };
  }, [question, patientId]);

  const parsedAnswer =
    conversation?.answer != null ? PatientAnswerSchema.safeParse(conversation.answer) : null;

  return (
    <div className="space-y-6">
      <p className="rounded bg-neutral-100 p-2 text-xs text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
        You asked: <span className="font-medium">{question}</span>
      </p>

      {phase === "loading" && (
        <p role="status" className="text-sm text-neutral-500">
          Starting the conversation…
        </p>
      )}

      {phase === "error" && (
        <p
          role="alert"
          className="rounded bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200"
        >
          {errorMessage}
        </p>
      )}

      {phase === "empty" && (
        <p
          role="status"
          className="rounded bg-neutral-100 p-3 text-sm text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400"
        >
          The conversation finished but produced no answer.
        </p>
      )}

      {(phase === "streaming" || phase === "success" || phase === "empty") && (
        <TraceTimeline events={events} />
      )}

      {phase === "success" && parsedAnswer?.success && (
        <>
          <GuardrailStrip answer={parsedAnswer.data} />
          <EvidencePanel answer={parsedAnswer.data} />
        </>
      )}

      {conversation && (phase === "success" || phase === "empty") && (
        <CostMeter conversation={conversation} />
      )}
    </div>
  );
}
