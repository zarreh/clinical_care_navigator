import { test } from "@playwright/test";
import path from "node:path";
import {
  ANSWERED_CONVERSATION,
  ANSWERED_SSE,
  ESCALATED_CONVERSATION,
  ESCALATED_SSE,
  PENDING_REVIEW,
} from "./fixtures";

// Captures the screenshots the docs walkthrough embeds. Reuses the exact same
// network mocks as conversation.spec.ts / reviews.spec.ts so a screenshot can
// never silently drift from what the smoke test proves the UI does
// (`make docs-screenshots`).
const SCREENSHOTS_DIR = path.join(__dirname, "..", "..", "docs", "assets");
const REVIEWS_API = /localhost:8000\/reviews$/;

async function mockCreate(page: import("@playwright/test").Page) {
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

async function mockConversation(
  page: import("@playwright/test").Page,
  id: string,
  sse: string,
  conversation: unknown
) {
  await page.route(`**/conversations/${id}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: sse });
  });
  await page.route(`**/conversations/${id}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(conversation),
    });
  });
}

test("capture: a full cited answer, streamed and checked", async ({ page }) => {
  await mockCreate(page);
  await mockConversation(page, "run-success", ANSWERED_SSE, ANSWERED_CONVERSATION);

  await page.goto("/");
  await page.getByLabel("Answer").waitFor();
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "screenshot-answer.png"),
    fullPage: true,
  });
});

test("capture: case 4 — a benign question over a critical value escalates", async ({ page }) => {
  await mockCreate(page);
  await mockConversation(page, "run-success", ANSWERED_SSE, ANSWERED_CONVERSATION);
  await mockConversation(page, "run-escalation", ESCALATED_SSE, ESCALATED_CONVERSATION);

  await page.goto("/");
  await page.getByLabel("Answer").waitFor();
  await page.getByRole("button", { name: "Show me an escalation (case 4)" }).click();
  await page.getByText("Pending clinician review").waitFor();
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "screenshot-escalation.png"),
    fullPage: true,
  });
});

test("capture: the clinician review queue", async ({ page }) => {
  await page.route(REVIEWS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([PENDING_REVIEW]),
    });
  });

  await page.goto("/reviews");
  await page.getByLabel("Review queue").waitFor();
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "screenshot-reviews.png"),
    fullPage: true,
  });
});
