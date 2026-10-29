"use client";

import Link from "next/link";
import {
  ArrowRight,
  Check,
  CircleCheck,
  Inbox,
  LoaderCircle,
  Pencil,
  RefreshCw,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ReasonBadge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/Card";
import { InfoTip } from "@/components/ui/InfoTip";
import {
  ApiError,
  decideReview,
  listReviews,
  type Persona,
  type ReviewAction,
  type ReviewSummary,
} from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary";
import { findPersona, personaSummary } from "@/lib/personas";
import { usePersonas } from "@/lib/usePersonas";
import { ACTION_LABELS, formatTimestamp } from "@/lib/run";

type Phase = "loading" | "ready" | "empty" | "error";

type Decided = { action: ReviewAction; runId: string; runStatus: string };

const DECIDED_TEXT: Record<ReviewAction, string> = {
  approve: "Approved. The draft is now published to the patient exactly as written.",
  edit: "Edited and published. The patient now sees your version.",
  decline: "Declined. The draft stays held and is never shown as answered.",
};

// The reviewer page (docs/PLAN.md §7): a clinician sees held drafts and can
// approve, edit, or decline. A decision resumes the suspended run from its
// checkpoint (§5.10). Nothing here is labelled approved until the reviewer
// acts (§3.7).
export function HITLDrawer() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [decided, setDecided] = useState<Decided | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { personas } = usePersonas();

  const refresh = useCallback(async () => {
    setPhase((p) => (p === "ready" ? p : "loading"));
    setErrorMessage(null);
    try {
      const items = await listReviews();
      setReviews(items);
      setPhase(items.length === 0 ? "empty" : "ready");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof ApiError ? error.message : "Could not load the review queue.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Card padded={false} className="flex items-center gap-4 px-5 py-3">
          <Inbox className="h-5 w-5 text-sky-600 dark:text-sky-400" aria-hidden />
          <div>
            <p className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">
              {phase === "ready" || phase === "empty" ? reviews.length : "–"}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              answer{reviews.length === 1 ? "" : "s"} waiting for a clinician
            </p>
          </div>
        </Card>
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-sky-500 hover:text-sky-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        >
          <RefreshCw className="h-4 w-4" aria-hidden /> Refresh
        </button>
      </div>

      {decided && (
        <Callout variant="success" role="status" title="Decision recorded">
          <span>
            {DECIDED_TEXT[decided.action]}{" "}
            <Link href={`/?run=${decided.runId}`} className="font-medium underline">
              See the run
            </Link>
          </span>
        </Callout>
      )}

      {notice && (
        <Callout variant="warning" role="status" title="Already decided">
          {notice}
        </Callout>
      )}

      {phase === "loading" && (
        <p role="status" className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden /> Loading the review queue…
        </p>
      )}

      {phase === "error" && (
        <Callout variant="error" role="alert" title="Could not load the review queue">
          {errorMessage}
        </Callout>
      )}

      {phase === "empty" && (
        <Callout role="status" title="No answers are pending review">
          Nothing is waiting. Answers land here when post-flight holds a draft, which a
          well-behaved model rarely produces. To see the clinician&apos;s role in a demo, load
          four sample drafts by running <code className="rounded bg-slate-200/60 px-1 py-0.5 font-mono text-xs dark:bg-slate-800">make seed-reviews</code>{" "}
          on the server, then refresh this page.
        </Callout>
      )}

      {phase === "ready" && (
        <ul className="space-y-4" aria-label="Review queue">
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              review={review}
              patient={findPersona(personas, review.patient_id)}
              onResolved={async (d) => {
                setNotice(null);
                setDecided(d);
                await refresh();
              }}
              onStale={async (message) => {
                setDecided(null);
                setNotice(message);
                await refresh();
              }}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function ReviewCard({
  review,
  patient,
  onResolved,
  onStale,
}: {
  review: ReviewSummary;
  patient: Persona | undefined;
  onResolved: (decided: Decided) => Promise<void>;
  onStale: (message: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editedBody, setEditedBody] = useState(review.body);
  const [busy, setBusy] = useState<ReviewAction | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  async function decide(action: ReviewAction) {
    setBusy(action);
    setCardError(null);
    try {
      const result = await decideReview(review.id, action, action === "edit" ? editedBody : undefined);
      await onResolved({ action, runId: result.run_id, runStatus: result.run_status });
    } catch (error) {
      setBusy(null);
      if (error instanceof ApiError && error.status === 409) {
        await onStale(error.message);
        return;
      }
      setCardError(error instanceof ApiError ? error.message : "Could not record that decision. Please try again.");
    }
  }

  const buttons: { action: ReviewAction; label: string; icon: typeof Check; consequence: string; className: string }[] = [
    {
      action: "approve",
      label: "Approve as written",
      icon: Check,
      consequence: "Publishes this exact draft to the patient.",
      className: "bg-emerald-600 text-white hover:bg-emerald-700",
    },
    editing
      ? {
          action: "edit",
          label: "Publish edited answer",
          icon: Pencil,
          consequence: "Publishes your edited text instead of the AI's.",
          className: "bg-sky-600 text-white hover:bg-sky-700",
        }
      : {
          action: "edit",
          label: "Edit before publishing",
          icon: Pencil,
          consequence: "Opens the draft so you can rewrite it first.",
          className:
            "border border-slate-300 bg-white text-slate-700 hover:border-sky-500 hover:text-sky-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200",
        },
    {
      action: "decline",
      label: "Decline",
      icon: X,
      consequence: "Keeps it held. The patient never sees it as answered.",
      className:
        "border border-red-300 bg-white text-red-700 hover:bg-red-50 dark:border-red-800 dark:bg-slate-900 dark:text-red-300 dark:hover:bg-red-950",
    },
  ];

  return (
    <li>
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 font-semibold text-amber-800 dark:bg-amber-900 dark:text-amber-200">
              Pending review
            </span>
            <span className="inline-flex items-center">
              Held because: <span className="ml-1"><ReasonBadge reason={review.reason} /></span>
              <InfoTip text={GLOSSARY.postFlight} />
            </span>
            {review.override_action && (
              <span>Suggested route: {ACTION_LABELS[review.override_action] ?? review.override_action}</span>
            )}
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">Held {formatTimestamp(review.created_at)}</span>
        </div>

        <p className="flex items-center gap-1.5 text-sm text-slate-700 dark:text-slate-200">
          <UserRound className="h-4 w-4 text-sky-600 dark:text-sky-400" aria-hidden />
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Patient
          </span>
          <span className="font-medium">
            {patient ? personaSummary(patient) : `patient ${review.patient_id.slice(0, 8)}`}
          </span>
        </p>

        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Draft the patient will see if you approve
          </p>
          {editing ? (
            <textarea
              aria-label="Edited answer"
              className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              rows={6}
              value={editedBody}
              onChange={(event) => setEditedBody(event.target.value)}
            />
          ) : (
            <blockquote className="whitespace-pre-line rounded-lg border-l-4 border-amber-400 bg-slate-50 p-3 text-sm leading-relaxed text-slate-800 dark:bg-slate-950 dark:text-slate-100">
              {review.body}
            </blockquote>
          )}
          <Link
            href={`/?run=${review.run_id}`}
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400"
          >
            See how this draft was produced, step by step <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
        </div>

        {cardError && (
          <Callout variant="error" role="alert">
            {cardError}
          </Callout>
        )}

        <div className="grid gap-3 sm:grid-cols-3">
          {buttons.map((b) => (
            <div key={b.label} className="space-y-1">
              <button
                type="button"
                disabled={busy !== null || (b.action === "edit" && editing && editedBody.trim() === "")}
                onClick={() => (b.action === "edit" && !editing ? setEditing(true) : void decide(b.action))}
                className={`inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${b.className}`}
              >
                {busy === b.action ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <b.icon className="h-4 w-4" aria-hidden />
                )}
                {b.label}
              </button>
              <p className="text-center text-xs text-slate-500 dark:text-slate-400">{b.consequence}</p>
            </div>
          ))}
        </div>
        {busy && (
          <p role="status" className="flex items-center gap-1.5 text-xs text-slate-500">
            <CircleCheck className="h-3.5 w-3.5" aria-hidden /> Resuming the paused run from its checkpoint…
          </p>
        )}
      </Card>
    </li>
  );
}
