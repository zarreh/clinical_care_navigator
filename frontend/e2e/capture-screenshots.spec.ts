import { test } from "@playwright/test";
import path from "node:path";
import {
  ANSWERED,
  API,
  FOLLOW_UP,
  HELD,
  OVERRIDE,
  PENDING_REVIEW,
  TWO_TURN_THREAD,
  mockPersonas,
  mockRuns,
} from "./fixtures";

// Captures the screenshots the docs walkthrough embeds, in light and dark.
// Reuses the exact same network mocks as conversation.spec.ts / reviews.spec.ts
// so a screenshot can never silently drift from what the smoke test proves the
// UI does (`make docs-screenshots`).
const SCREENSHOTS_DIR = path.join(__dirname, "..", "..", "docs", "assets");
const REVIEWS_API = /localhost:8000\/reviews$/;

for (const scheme of ["light", "dark"] as const) {
  const file = (name: string) =>
    path.join(SCREENSHOTS_DIR, `screenshot-${name}${scheme === "dark" ? "-dark" : ""}.png`);

  test.describe(`${scheme} mode`, () => {
    test.use({ colorScheme: scheme, viewport: { width: 1280, height: 900 } });

    // A sticky header lands mid-image in a full-page capture; pin it to the top.
    test.beforeEach(async ({ page }) => {
      page.on("load", () => void page.addStyleTag({ content: "header.sticky { position: static !important; }" }));
    });

    test.beforeEach(async ({ page }) => {
      await mockPersonas(page);
    });

    test("capture: the homepage", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("heading", { name: /How it works/ }).waitFor();
      await page.screenshot({ path: file("home"), fullPage: true });
    });

    test("capture: a full cited answer, streamed and checked", async ({ page }) => {
      await mockRuns(page);
      await page.goto(`/?run=${ANSWERED.id}`);
      await page.getByLabel("Outcome", { exact: true }).waitFor();
      await page.getByLabel("Run summary", { exact: true }).scrollIntoViewIfNeeded();
      await page.screenshot({ path: file("answer"), fullPage: true });
    });

    test("capture: case 4, a benign question over a critical value is overridden", async ({ page }) => {
      await mockRuns(page);
      await page.goto(`/?run=${OVERRIDE.id}`);
      await page.getByLabel("Outcome", { exact: true }).waitFor();
      await page.screenshot({ path: file("escalation"), fullPage: true });
    });

    test("capture: a follow-up conversation", async ({ page }) => {
      await mockRuns(page, [ANSWERED, FOLLOW_UP]);
      await page.route(`${API}/conversations/run-follow/thread`, (route) =>
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(TWO_TURN_THREAD) })
      );
      await page.goto(`/?run=${FOLLOW_UP.id}`);
      await page.getByLabel("Follow-up", { exact: true }).waitFor();
      await page.screenshot({ path: file("followup"), fullPage: true });
    });

    test("capture: a draft held for a clinician", async ({ page }) => {
      await mockRuns(page);
      await page.goto(`/?run=${HELD.id}`);
      await page.getByLabel("Outcome", { exact: true }).waitFor();
      await page.screenshot({ path: file("held"), fullPage: true });
    });

    test("capture: the clinician review queue", async ({ page }) => {
      await page.route(REVIEWS_API, (route) =>
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([PENDING_REVIEW]) })
      );
      await page.goto("/reviews");
      await page.getByLabel("Review queue", { exact: true }).waitFor();
      await page.screenshot({ path: file("reviews"), fullPage: true });
    });
  });
}
