import { test, expect, type Page } from "@playwright/test";
import {
  ANSWERED_CONVERSATION,
  ANSWERED_SSE,
  EMPTY_SSE,
  ESCALATED_CONVERSATION,
  ESCALATED_SSE,
  MEDLINEPLUS_URL,
} from "./fixtures";

// Every state a conversation can render (docs/PLAN.md §7: "Tested loading,
// success, empty and error states"), plus the two Phase 7 exit behaviours: a
// visitor can open a citation, and can trigger case 4 and see the escalation
// without typing anything. The backend is fully mocked at the network layer.

async function mockConversation(
  page: Page,
  opts: { id: string; sse: string; conversation: unknown }
) {
  await page.route(`**/conversations/${opts.id}/events`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: opts.sse,
    });
  });
  await page.route(`**/conversations/${opts.id}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(opts.conversation),
    });
  });
}

/** Routes POST /conversations to a run id chosen from the question, so the home
 * page's two scenario buttons resolve to the two mocked runs. */
async function mockCreate(page: Page) {
  await page.route("**/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON() as { question: string };
    const id = body.question.toLowerCase().includes("potassium")
      ? "run-escalation"
      : "run-success";
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id, status: "running" }),
    });
  });
}

test("loading: shows a starting message before the run begins", async ({ page }) => {
  await page.route("**/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: "run-loading", status: "running" }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("Starting the conversation")).toBeVisible();
});

test("success: renders the trace, guardrail status, the answer, and a clickable citation", async ({
  page,
}) => {
  await mockCreate(page);
  await mockConversation(page, {
    id: "run-success",
    sse: ANSWERED_SSE,
    conversation: ANSWERED_CONVERSATION,
  });

  await page.goto("/");
  await expect(page.getByLabel("Trace")).toBeVisible();
  await expect(page.getByLabel("Answer")).toBeVisible();
  await expect(page.getByText("Answered", { exact: true })).toBeVisible();
  await expect(page.getByText("Post-flight passed")).toBeVisible();
  await expect(page.getByLabel("Cost")).toBeVisible();
  await expect(page.getByLabel("Cost").getByText("$0.0021").first()).toBeVisible();
  // Reading level is shown, so the assistant adapts *with* the reader (§3.7).
  await expect(page.getByText("reading level of grade 6.0")).toBeVisible();

  // A citation nobody can open is not a citation (§6.1): the MedlinePlus source
  // is a real, clickable link.
  const citation = page.getByRole("link", { name: "MedlinePlus: Hemoglobin A1C" });
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute("href", MEDLINEPLUS_URL);
});

test("escalation: triggering case 4 shows the answer held for clinician review", async ({
  page,
}) => {
  await mockCreate(page);
  await mockConversation(page, {
    id: "run-success",
    sse: ANSWERED_SSE,
    conversation: ANSWERED_CONVERSATION,
  });
  await mockConversation(page, {
    id: "run-escalation",
    sse: ESCALATED_SSE,
    conversation: ESCALATED_CONVERSATION,
  });

  await page.goto("/");
  await expect(page.getByLabel("Answer")).toBeVisible();

  // No typing: a single click triggers case 4.
  await page.getByRole("button", { name: "Show me an escalation (case 4)" }).click();

  await expect(page.getByText("Pending clinician review")).toBeVisible();
  await expect(page.getByText("Post-flight escalated")).toBeVisible();
  await expect(page.getByText("held for a clinician to review")).toBeVisible();
  // The escalation step appears in the trace.
  await expect(page.getByText("Holding the answer for clinician review")).toBeVisible();
  // Pending is never rendered as approved (§3.7).
  await expect(page.getByText("approved", { exact: false })).toHaveCount(1);
});

test("empty: renders a defensive message when a completed run has no answer", async ({
  page,
}) => {
  await mockCreate(page);
  await mockConversation(page, {
    id: "run-success",
    sse: EMPTY_SSE,
    conversation: { ...ANSWERED_CONVERSATION, answer_kind: null, answer: null, costs: [], total_cost_usd: 0 },
  });

  await page.goto("/");
  await expect(page.getByText("produced no answer")).toBeVisible();
});

test("error: renders an alert when the conversation cannot be started", async ({ page }) => {
  await page.route("**/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
  });

  await page.goto("/");
  await expect(page.getByText("Could not start the conversation")).toBeVisible();
});
