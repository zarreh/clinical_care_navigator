import { TraceEventSchema, type TraceEvent } from "./schemas";
import type { components } from "./api-types";

export type CreateConversationResponse =
  components["schemas"]["CreateConversationResponse"];
export type ConversationResponse = components["schemas"]["ConversationResponse"];
export type CostSummaryEntry = components["schemas"]["CostSummaryEntry"];
export type ReviewSummary = components["schemas"]["ReviewSummary"];
export type ReviewDecisionResponse = components["schemas"]["ReviewDecisionResponse"];
export type ReviewAction = components["schemas"]["ReviewDecisionRequest"]["action"];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

export async function createConversation(
  question: string,
  patientId?: string
): Promise<CreateConversationResponse> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, patient_id: patientId ?? null }),
  });
  if (!response.ok) {
    throw new ApiError(`Failed to start conversation (${response.status})`, response.status);
  }
  return response.json() as Promise<CreateConversationResponse>;
}

export async function getConversation(id: string): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE}/conversations/${id}`);
  if (!response.ok) {
    throw new ApiError(`Failed to fetch conversation (${response.status})`, response.status);
  }
  return response.json() as Promise<ConversationResponse>;
}

export type TraceEventHandlers = {
  onEvent: (event: TraceEvent) => void;
  onEnd: () => void;
  onError: () => void;
};

/** Subscribes to GET /conversations/{id}/events (SSE). Returns a cleanup
 * function that closes the connection — call it on unmount. */
export function streamConversationEvents(id: string, handlers: TraceEventHandlers): () => void {
  const source = new EventSource(`${API_BASE}/conversations/${id}/events`);
  source.onmessage = (message) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(message.data as string);
    } catch {
      handlers.onError();
      return;
    }
    const result = TraceEventSchema.safeParse(parsed);
    if (!result.success) {
      handlers.onError();
      return;
    }
    handlers.onEvent(result.data);
    if (result.data.node === "__end__") {
      source.close();
      handlers.onEnd();
    }
  };
  source.onerror = () => {
    source.close();
    handlers.onError();
  };
  return () => source.close();
}

export async function listReviews(): Promise<ReviewSummary[]> {
  const response = await fetch(`${API_BASE}/reviews`);
  if (!response.ok) {
    throw new ApiError(`Failed to fetch the review queue (${response.status})`, response.status);
  }
  return response.json() as Promise<ReviewSummary[]>;
}

export async function decideReview(
  reviewId: string,
  action: ReviewAction,
  editedBody?: string
): Promise<ReviewDecisionResponse> {
  const response = await fetch(`${API_BASE}/reviews/${reviewId}/decision`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action, edited_body: editedBody ?? null }),
  });
  if (!response.ok) {
    throw new ApiError(`Failed to record the decision (${response.status})`, response.status);
  }
  return response.json() as Promise<ReviewDecisionResponse>;
}
