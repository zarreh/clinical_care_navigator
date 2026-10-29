import { test, expect } from "@playwright/test";
import { PENDING_REVIEW, mockPersonas } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockPersonas(page);
});

// The clinician review queue (docs/PLAN.md §7). Loading, empty, error, the
// approve flow that resumes a suspended run, and the 409 a second reviewer
// gets. Fully network-mocked.
//
// The routes are scoped to the API host with a regexp: a bare "**/reviews" glob
// would also intercept the Next.js page navigation to /reviews itself.
const REVIEWS_API = /localhost:8000\/reviews$/;
const DECISION_API = /localhost:8000\/reviews\/review-1\/decision$/;

test("empty: shows a message when nothing is pending", async ({ page }) => {
  await page.route(REVIEWS_API, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.goto("/reviews");
  await expect(page.getByText("No answers are pending review")).toBeVisible();
  await expect(page.getByText("Demo only: this page has no login")).toBeVisible();
});

test("error: shows an alert when the queue cannot be loaded", async ({ page }) => {
  await page.route(REVIEWS_API, (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: "{}" })
  );
  await page.goto("/reviews");
  await expect(page.getByRole("alert").getByText("Could not load the review queue").first()).toBeVisible();
});

test("approve: a held draft can be approved and then leaves the queue", async ({ page }) => {
  let resolved = false;
  await page.route(REVIEWS_API, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resolved ? [] : [PENDING_REVIEW]),
    })
  );
  await page.route(DECISION_API, async (route) => {
    resolved = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ review_id: "review-1", run_id: PENDING_REVIEW.run_id, action: "approve", run_status: "answered" }),
    });
  });

  await page.goto("/reviews");
  const queue = page.getByLabel("Review queue", { exact: true });
  await expect(queue).toBeVisible();
  // Pending is labelled as pending, never approved (§3.7).
  await expect(queue.getByText("Pending review", { exact: true })).toBeVisible();
  await expect(queue.getByText("Flagged by the scope check")).toBeVisible();
  await expect(queue.getByRole("link", { name: /step by step/ })).toHaveAttribute("href", `/?run=${PENDING_REVIEW.run_id}`);
  await expect(queue.getByText("Publishes this exact draft to the patient.")).toBeVisible();
  // A clinician needs to know whose record the draft is about.
  await expect(queue.getByText("Margaret Ellison, 82, English, reading target grade 8")).toBeVisible();

  await page.getByRole("button", { name: "Approve as written" }).click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  await expect(page.getByText("No answers are pending review")).toBeVisible();
});

test("conflict: a review someone else already decided says so and refreshes", async ({ page }) => {
  let decided = false;
  await page.route(REVIEWS_API, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(decided ? [] : [PENDING_REVIEW]),
    })
  );
  await page.route(DECISION_API, async (route) => {
    decided = true;
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "This review is already approved; refresh the queue to see its outcome." }),
    });
  });

  await page.goto("/reviews");
  await page.getByRole("button", { name: "Decline" }).click();
  await expect(page.getByText("This review is already approved")).toBeVisible();
  await expect(page.getByText("No answers are pending review")).toBeVisible();
});
