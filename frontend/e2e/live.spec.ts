import { expect, test, type Page } from "@playwright/test";

// Unmocked: needs the API on :8000 with a real key and built data. Costs a few model calls,
// so it only runs on request (LIVE_E2E=1 npx playwright test live.spec.ts).
test.skip(!process.env.LIVE_E2E, "set LIVE_E2E=1 to run against the real API");
test.setTimeout(150_000);

test.beforeEach(({ page }) => {
  page.on("requestfailed", (request) => {
    // Navigating away deliberately cancels an event stream.
    if (request.failure()?.errorText === "net::ERR_ABORTED") return;
    throw new Error(`request failed: ${request.url()} ${request.failure()?.errorText}`);
  });
});

async function runScenario(page: Page, question: string) {
  await page.goto("/");
  await page.getByRole("listitem").filter({ hasText: question }).getByRole("button", { name: "Run this question" }).click();
  await expect(page.getByLabel("Outcome", { exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
}

test("a real answer streams in, is checked, and shows real cost", async ({ page }) => {
  await runScenario(page, "What is an A1c test?");
  await expect(page.getByLabel("Trace", { exact: true })).toBeVisible();
  const cost = page.getByLabel("Cost", { exact: true });
  await expect(cost).toBeVisible();
  // Cost rows must name a real model, not "unknown".
  await expect(cost.getByText("unknown")).toHaveCount(0);

  // The run is addressable: a reload replays it from the store.
  await page.reload();
  await expect(page.getByLabel("Outcome", { exact: true })).toBeVisible({ timeout: 30_000 });
});

test("the critical-value scenario shows the planted potassium as a safety override", async ({ page }) => {
  await runScenario(page, "What does my potassium of 6.9 mean?");
  const answer = page.getByLabel("Answer", { exact: true });
  await expect(answer.getByText(/Potassium at 6\.9 mmol\/L/)).toBeVisible();
  await expect(answer.getByText(/critical-high level/)).toBeVisible();
  await expect(answer.getByText("Safe templated response")).toBeVisible();
});

test("the emergency scenario is answered by pre-flight without the AI", async ({ page }) => {
  await runScenario(page, "I have crushing chest pain and my left arm is numb.");
  await expect(page.getByLabel("Outcome", { exact: true }).getByText(/Emergency guidance/)).toBeVisible();
});
