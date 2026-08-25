import { test, expect } from "@playwright/test";
import { PENDING_REVIEW } from "./fixtures";

// The clinician review queue (docs/PLAN.md §7). Loading, empty, error, and the
// approve flow that resumes a suspended run. Fully network-mocked.
//
// The routes are scoped to the API host with a regexp: a bare "**/reviews" glob
// would also intercept the Next.js page navigation to /reviews itself, since
// both share the same path.
const REVIEWS_API = /localhost:8000\/reviews$/;
const DECISION_API = /localhost:8000\/reviews\/review-1\/decision$/;

test("empty: shows a message when nothing is pending", async ({ page }) => {
  await page.route(REVIEWS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto("/reviews");
  await expect(page.getByText("No answers are pending review")).toBeVisible();
});

test("error: shows an alert when the queue cannot be loaded", async ({ page }) => {
  await page.route(REVIEWS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
  });

  await page.goto("/reviews");
  await expect(page.getByText("Could not load the review queue")).toBeVisible();
});

test("approve: a held draft can be approved and then leaves the queue", async ({ page }) => {
  let resolved = false;
  await page.route(REVIEWS_API, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resolved ? [] : [PENDING_REVIEW]),
    });
  });
  await page.route(DECISION_API, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    resolved = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        review_id: "review-1",
        run_id: PENDING_REVIEW.run_id,
        action: "approve",
        run_status: "answered",
      }),
    });
  });

  await page.goto("/reviews");
  await expect(page.getByLabel("Review queue")).toBeVisible();
  // Pending is labelled as pending, never approved (§3.7).
  await expect(page.getByText("Pending review")).toBeVisible();
  await expect(page.getByText("Reason: critical_value")).toBeVisible();

  await page.getByRole("button", { name: "Approve as written" }).click();
  await expect(page.getByText("No answers are pending review")).toBeVisible();
});
