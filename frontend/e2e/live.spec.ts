import { expect, test } from "@playwright/test";

// Unmocked: needs the API on :8000 with a real key and built data. Costs a few model calls,
// so it only runs on request (LIVE_E2E=1 npx playwright test live.spec.ts).
test.skip(!process.env.LIVE_E2E, "set LIVE_E2E=1 to run against the real API");
test.setTimeout(150_000);

test.beforeEach(({ page }) => {
  page.on("requestfailed", (request) => {
    throw new Error(`request failed: ${request.url()} ${request.failure()?.errorText}`);
  });
});

test("a real answer streams in, is cited, and shows real cost", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByLabel("Answer")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByLabel("Trace")).toBeVisible();

  // Cost rows must name a real model, not "unknown".
  const cost = page.getByLabel("Cost");
  await expect(cost).toBeVisible();
  await expect(cost.getByText("unknown")).toHaveCount(0);
});

test("the escalation button shows a real post-flight escalation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Answer")).toBeVisible({ timeout: 120_000 });

  await page.getByRole("button", { name: "Show me an escalation (case 4)" }).click();

  await expect(page.getByText("Post-flight escalated")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});
