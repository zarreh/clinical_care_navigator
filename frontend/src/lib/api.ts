import { TraceEventSchema, type TraceEvent } from "./schemas";
import type { components } from "./api-types";

export type CreateConversationResponse =
  components["schemas"]["CreateConversationResponse"];
export type ConversationResponse = components["schemas"]["ConversationResponse"];
export type CostSummaryEntry = components["schemas"]["CostSummaryEntry"];
export type ReviewSummary = components["schemas"]["ReviewSummary"];
export type ReviewDecisionResponse = components["schemas"]["ReviewDecisionResponse"];
export type ThreadResponse = components["schemas"]["ThreadResponse"];
export type ThreadTurn = components["schemas"]["ThreadTurn"];
export type Persona = components["schemas"]["PersonaResponse"];
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

/** A sentence a visitor can act on, built from the status and the API's own
 * `detail` (which explains *why*), instead of a bare "failed (500)". */
async function apiError(response: Response, action: string): Promise<ApiError> {
  let detail: string | null = null;
  try {
    const body = (await response.json()) as { detail?: unknown; error?: unknown };
    const raw = body.detail ?? body.error;
    if (typeof raw === "string") detail = raw;
  } catch {
    // Non-JSON body: fall back to the status-based message.
  }
  const status = response.status;
  let message: string;
  if (status === 429) {
    message = `Too many requests from your connection. Wait about a minute, then try again.`;
  } else if (status === 404) {
    message = `${action}: ${detail ?? "not found"}.`;
  } else if (status === 409) {
    message = detail ?? `${action}: someone else already acted on this.`;
  } else if (status >= 500) {
    message = `${action}: the server had a problem${detail ? ` (${detail})` : ""}. Please try again.`;
  } else {
    message = `${action}${detail ? `: ${detail}` : ` (HTTP ${status})`}.`;
  }
  return new ApiError(message, status);
}

/** Network failures (API down, CORS) never reach `response`, so say so plainly. */
async function request(url: string, init: RequestInit | undefined, action: string): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    // A browser reports "API down" and "blocked by CORS" identically, so name both.
    const origin = typeof window !== "undefined" ? window.location.origin : "this page";
    throw new ApiError(
      `${action}: the API at ${API_BASE} did not answer. Check that it is running, and that ` +
        `${origin} is in its NAVIGATOR_FRONTEND_ORIGINS (a browser blocks the call otherwise).`,
      0
    );
  }
  if (!response.ok) throw await apiError(response, action);
  return response;
}

export async function createConversation(
  question: string,
  patientId?: string,
  followUpTo?: string
): Promise<CreateConversationResponse> {
  const response = await request(
    `${API_BASE}/conversations`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        question,
        patient_id: patientId ?? null,
        ...(followUpTo ? { follow_up_to: followUpTo } : {}),
      }),
    },
    "Could not start the conversation"
  );
  return response.json() as Promise<CreateConversationResponse>;
}

export async function getConversation(id: string): Promise<ConversationResponse> {
  const response = await request(
    `${API_BASE}/conversations/${id}`,
    undefined,
    "Could not load this conversation"
  );
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
  const response = await request(`${API_BASE}/reviews`, undefined, "Could not load the review queue");
  return response.json() as Promise<ReviewSummary[]>;
}

export async function decideReview(
  reviewId: string,
  action: ReviewAction,
  editedBody?: string
): Promise<ReviewDecisionResponse> {
  const response = await request(
    `${API_BASE}/reviews/${reviewId}/decision`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, edited_body: editedBody ?? null }),
    },
    "Could not record the decision"
  );
  return response.json() as Promise<ReviewDecisionResponse>;
}

export async function listPersonas(): Promise<Persona[]> {
  const response = await request(`${API_BASE}/personas`, undefined, "Could not load the demo patients");
  return response.json() as Promise<Persona[]>;
}

export async function getThread(runId: string): Promise<ThreadResponse> {
  const response = await request(
    `${API_BASE}/conversations/${runId}/thread`,
    undefined,
    "Could not load this conversation"
  );
  return response.json() as Promise<ThreadResponse>;
}
