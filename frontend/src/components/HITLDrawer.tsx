"use client";

import { useCallback, useEffect, useState } from "react";
import {
  decideReview,
  listReviews,
  type ReviewAction,
  type ReviewSummary,
} from "@/lib/api";

type Phase = "loading" | "ready" | "empty" | "error";

// The reviewer page (docs/PLAN.md §7): a clinician sees held drafts and can
// approve, edit, or decline. A decision resumes the suspended run from its
// checkpoint (§5.10). Nothing here is labelled approved until the reviewer
// acts (§3.7).
export function HITLDrawer() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setPhase("loading");
    setErrorMessage(null);
    try {
      const items = await listReviews();
      setReviews(items);
      setPhase(items.length === 0 ? "empty" : "ready");
    } catch {
      setPhase("error");
      setErrorMessage("Could not load the review queue.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (phase === "loading") {
    return (
      <p role="status" className="text-sm text-neutral-500">
        Loading the review queue…
      </p>
    );
  }

  if (phase === "error") {
    return (
      <p
        role="alert"
        className="rounded bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200"
      >
        {errorMessage}
      </p>
    );
  }

  if (phase === "empty") {
    return (
      <p
        role="status"
        className="rounded bg-neutral-100 p-3 text-sm text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400"
      >
        No answers are pending review.
      </p>
    );
  }

  return (
    <ul className="space-y-4" aria-label="Review queue">
      {reviews.map((review) => (
        <ReviewCard key={review.id} review={review} onResolved={refresh} />
      ))}
    </ul>
  );
}

function ReviewCard({
  review,
  onResolved,
}: {
  review: ReviewSummary;
  onResolved: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editedBody, setEditedBody] = useState(review.body);
  const [busy, setBusy] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);

  async function decide(action: ReviewAction) {
    setBusy(true);
    setCardError(null);
    try {
      await decideReview(review.id, action, action === "edit" ? editedBody : undefined);
      await onResolved();
    } catch {
      setBusy(false);
      setCardError("Could not record that decision. Please try again.");
    }
  }

  return (
    <li className="space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <span className="rounded bg-amber-100 px-2 py-1 font-semibold uppercase text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Pending review
        </span>
        <span>Reason: {review.reason}</span>
        {review.override_action && <span>Override: {review.override_action}</span>}
        <span className="font-mono">run {review.run_id.slice(0, 8)}</span>
      </div>

      {editing ? (
        <textarea
          aria-label="Edited answer"
          className="w-full rounded border border-neutral-300 p-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          rows={5}
          value={editedBody}
          onChange={(event) => setEditedBody(event.target.value)}
        />
      ) : (
        <p className="whitespace-pre-line text-sm">{review.body}</p>
      )}

      {cardError && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-300">
          {cardError}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void decide("approve")}
          className="rounded bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Approve as written
        </button>
        {editing ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void decide("edit")}
            className="rounded bg-blue-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            Publish edited answer
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => setEditing(true)}
            className="rounded border border-neutral-400 px-3 py-1.5 text-sm text-neutral-700 dark:border-neutral-600 dark:text-neutral-300"
          >
            Edit before publishing
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => void decide("decline")}
          className="rounded border border-red-400 px-3 py-1.5 text-sm text-red-700 disabled:opacity-50 dark:border-red-800 dark:text-red-300"
        >
          Decline
        </button>
      </div>
    </li>
  );
}
