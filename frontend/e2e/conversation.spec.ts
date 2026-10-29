import { test, expect } from "@playwright/test";
import {
  ANSWERED,
  API,
  BASIC_ID,
  CRITICAL_ID,
  EMERGENCY,
  FOLLOW_UP,
  FOLLOW_UP_QUESTION,
  HELD,
  MEDLINEPLUS_URL,
  OVERRIDE,
  REWRITE,
  STATPEARLS_URL,
  TWO_TURN_THREAD,
  mockCreate,
  mockPersonas,
  mockRuns,
} from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockPersonas(page);
});

// Every state a conversation can render (docs/PLAN.md §7: loading, success,
// empty and error), each of the four outcomes, and the two behaviours behind
// the "slow, broken UI" fix: nothing runs until the visitor asks, and a run is
// addressable by URL so a refresh replays it. The backend is fully mocked.

test("first paint explains the app and starts no run until asked", async ({ page }) => {
  const calls = await mockCreate(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /How it works/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run this question" })).toHaveCount(4);
  await expect(page.getByLabel("Ask your own question")).toBeVisible();
  await page.waitForTimeout(500);
  expect(calls.count).toBe(0);
});

test("loading: shows a starting message while the run is created", async ({ page }) => {
  await page.route(`${API}/conversations`, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ id: "x", status: "running" }) });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Run this question" }).first().click();
  await expect(page.getByText("Starting the conversation")).toBeVisible();
});

test("answered: trace, outcome, claim check, cost, and a clickable citation", async ({ page }) => {
  await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Run this question" }).first().click();

  await expect(page).toHaveURL(/run=run-success/);
  await expect(page.getByLabel("Outcome", { exact: true }).getByText("Published to you")).toBeVisible();
  await expect(page.getByLabel("Trace", { exact: true }).getByText("Lab education (92% confident)")).toBeVisible();
  await expect(page.getByLabel("Trace", { exact: true }).getByText("Allowed to answer · band: inform")).toBeVisible();
  await expect(page.getByLabel("Answer", { exact: true }).getByText("Answered", { exact: true })).toBeVisible();
  await expect(page.getByText("target grade 6.0")).toBeVisible();
  await expect(page.getByLabel("Claim check", { exact: true }).getByLabel("Supported")).toHaveCount(2);
  await expect(page.getByLabel("Cost", { exact: true }).getByText("$0.0021").first()).toBeVisible();

  // A citation nobody can open is not a citation (§6.1).
  const citation = page.getByRole("link", { name: "MedlinePlus: Hemoglobin A1C" });
  await expect(citation).toHaveAttribute("href", MEDLINEPLUS_URL);
});

test("a run is addressable: loading /?run=<id> replays it without starting a new one", async ({ page }) => {
  const calls = await mockCreate(page);
  await mockRuns(page);
  await page.goto(`/?run=${ANSWERED.id}`);
  await expect(page.getByLabel("Outcome", { exact: true }).getByText("Published to you")).toBeVisible();
  expect(calls.count).toBe(0);
});

test("free text: a typed question starts a run", async ({ page }) => {
  await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");
  await page.getByLabel("Ask your own question").fill(ANSWERED.question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByLabel("Run summary", { exact: true }).getByText(ANSWERED.question)).toBeVisible();
});

test("held: a draft post-flight will not publish is labelled pending, never approved", async ({ page }) => {
  await mockRuns(page);
  await page.goto(`/?run=${HELD.id}`);
  const outcome = page.getByLabel("Outcome", { exact: true });
  await expect(outcome.getByRole("heading", { name: "Held for a clinician" })).toBeVisible();
  await expect(outcome.getByRole("link", { name: /review queue/ })).toHaveAttribute("href", "/reviews");
  await expect(page.getByLabel("Answer", { exact: true }).getByText("Pending clinician review")).toBeVisible();
  await expect(page.getByText("The AI judge flagged the draft")).toBeVisible();
  await expect(page.getByText("Published to you")).toHaveCount(0);
});

test("emergency: pre-flight answers before the AI and the skipped stages say so", async ({ page }) => {
  await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");
  await page.getByRole("listitem").filter({ hasText: EMERGENCY.question }).getByRole("button").click();

  await expect(page.getByLabel("Outcome", { exact: true }).getByText("Emergency guidance, right away")).toBeVisible();
  await expect(page.getByLabel("Run progress", { exact: true }).getByText("Skipped")).toHaveCount(3);
  await expect(page.getByLabel("Claim check", { exact: true }).getByText(/Not needed/)).toBeVisible();
  await expect(page.getByLabel("Trace", { exact: true }).getByText("Matched “crushing chest pain”")).toBeVisible();
});

test("critical value: post-flight overrides the draft and links the threshold source", async ({ page }) => {
  await mockRuns(page);
  await page.goto(`/?run=${OVERRIDE.id}`);
  const outcome = page.getByLabel("Outcome", { exact: true });
  await expect(outcome.getByText("Safety override after checking the record")).toBeVisible();
  await expect(outcome.getByText(/Potassium at 6\.9 mmol\/L/)).toBeVisible();
  await expect(outcome.getByRole("link", { name: /Threshold source/ })).toHaveAttribute("href", STATPEARLS_URL);
  await expect(page.getByLabel("Answer", { exact: true }).getByText("Safe templated response")).toBeVisible();
});

test("empty: a completed run with no answer says so", async ({ page }) => {
  const empty = {
    ...ANSWERED,
    sse: ANSWERED.sse,
    conversation: { ...(ANSWERED.conversation as object), answer: null, costs: [], total_cost_usd: 0 },
  };
  await mockRuns(page, [empty]);
  await page.goto(`/?run=${ANSWERED.id}`);
  await expect(page.getByText("produced no answer")).toBeVisible();
});

test("failed: a failed run shows its stored error", async ({ page }) => {
  const failed = {
    ...ANSWERED,
    conversation: { ...(ANSWERED.conversation as object), status: "failed", answer: null, error: "interrupted by a server restart before it finished" },
  };
  await mockRuns(page, [failed]);
  await page.goto(`/?run=${ANSWERED.id}`);
  await expect(page.getByRole("alert").getByText(/interrupted by a server restart/)).toBeVisible();
});

test("unknown run id explains that the run no longer exists", async ({ page }) => {
  await page.route(`${API}/conversations/gone`, (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "conversation not found" }) })
  );
  await page.goto("/?run=gone");
  await expect(page.getByText("This run no longer exists")).toBeVisible();
});

test("rate limited: the visitor is told to wait, not shown a generic failure", async ({ page }) => {
  await page.route(`${API}/conversations`, (route) =>
    route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ error: "Rate limit exceeded: 10 per 1 minute" }) })
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Run this question" }).first().click();
  await expect(page.getByRole("alert").getByText(/Too many requests/)).toBeVisible();
});

test("server error: the API's detail reaches the visitor", async ({ page }) => {
  await page.route(`${API}/conversations`, (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "no patient records available" }) })
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Run this question" }).first().click();
  await expect(page.getByRole("alert").getByText(/no patient records available/)).toBeVisible();
});

test("the picker offers the demo patients and starts on the first, with no run started", async ({ page }) => {
  const calls = await mockCreate(page);
  await page.goto("/");

  const picker = page.getByRole("radiogroup", { name: "Who are you asking as?" });
  await expect(picker.getByRole("radio")).toHaveCount(3);
  await expect(picker.getByRole("radio", { name: /Margaret Ellison/ })).toHaveAttribute("aria-checked", "true");
  // The history is shown so a visitor can see why the patient is worth asking about.
  await expect(picker.getByText(/7,647 lab results across 58 tests/)).toBeVisible();
  await expect(picker.getByText("Basic literacy · grade 6").first()).toBeVisible();
  expect(calls.count).toBe(0);
});

test("choosing a patient keeps the choice in the URL and sends it with a typed question", async ({ page }) => {
  const calls = await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");

  await page.getByRole("radio", { name: /Rosa Delgado/ }).click();
  await expect(page).toHaveURL(new RegExp(`patient=${BASIC_ID}`));
  await expect(page.getByRole("radio", { name: /Rosa Delgado/ })).toHaveAttribute("aria-checked", "true");

  await page.getByLabel("Or ask your own question").fill(ANSWERED.question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByLabel("Run summary", { exact: true })).toBeVisible();
  expect(calls.bodies.at(-1)?.patient_id).toBe(BASIC_ID);
  await expect(page).toHaveURL(new RegExp(`patient=${BASIC_ID}.*run=|run=.*patient=${BASIC_ID}`));
});

test("a shared link keeps who the question was asked as", async ({ page }) => {
  await mockRuns(page);
  await page.goto(`/?patient=${CRITICAL_ID}`);
  await expect(page.getByRole("radio", { name: /Daniel Whitaker/ })).toHaveAttribute("aria-checked", "true");
});

test("the critical-value scenario asks as the patient whose record has it", async ({ page }) => {
  const calls = await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");

  const card = page.getByRole("listitem").filter({ hasText: OVERRIDE.question });
  await expect(card.getByText(/Asks as:\s*Daniel Whitaker/)).toBeVisible();
  await card.getByRole("button", { name: "Run this question" }).click();

  await expect(page.getByLabel("Outcome", { exact: true })).toBeVisible();
  expect(calls.bodies.at(-1)?.patient_id).toBe(CRITICAL_ID);
  // The picker follows the scenario, so what is on screen matches who was asked.
  await expect(page.getByRole("radio", { name: /Daniel Whitaker/ })).toHaveAttribute("aria-checked", "true");
});

test("the run says who it was asked as, including their reading target", async ({ page }) => {
  await mockRuns(page);
  await page.goto(`/?run=${ANSWERED.id}`);
  await expect(page.getByLabel("Run summary", { exact: true })).toContainText(
    `Asked as Margaret Ellison, 82, English, reading target grade 8`
  );
});

test("if the demo patients cannot load, the visitor is told and can still ask", async ({ page }) => {
  await page.route(`${API}/personas`, (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) })
  );
  const calls = await mockCreate(page);
  await mockRuns(page);
  await page.goto("/");

  await expect(page.getByRole("alert").getByText("Demo patients unavailable")).toBeVisible();
  await page.getByLabel("Or ask your own question").fill(ANSWERED.question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByLabel("Outcome", { exact: true })).toBeVisible();
  // No patient was chosen, so the server's default applies.
  expect(calls.bodies.at(-1)?.patient_id ?? null).toBeNull();
});

test("an unreachable API says what to check, including the allowed-origins setting", async ({ page }) => {
  await page.route(`${API}/personas`, (route) => route.abort("failed"));
  await page.goto("/");

  const alert = page.getByRole("alert").filter({ hasText: "Demo patients unavailable" });
  await expect(alert).toContainText("did not answer");
  await expect(alert).toContainText("NAVIGATOR_FRONTEND_ORIGINS");
  await expect(alert).toContainText("http://localhost:3100");
});

// --- conversational follow-ups --------------------------------------------------

/** Routes POST /conversations: a follow-up (has follow_up_to) starts run-follow; a fresh
 * question starts run-success. Records every body. */
async function mockFollowUpFlow(page: import("@playwright/test").Page) {
  const bodies: { question: string; patient_id?: string | null; follow_up_to?: string }[] = [];
  await mockRuns(page, [ANSWERED, FOLLOW_UP]);
  // Once the follow-up exists, either turn's thread has both turns.
  let followedUp = false;
  await page.route(`${API}/conversations/run-success/thread`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        followedUp
          ? TWO_TURN_THREAD
          : { ...TWO_TURN_THREAD, turns: TWO_TURN_THREAD.turns.slice(0, 1) }
      ),
    })
  );
  await page.route(`${API}/conversations/run-follow/thread`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(TWO_TURN_THREAD) })
  );
  await page.route(`${API}/conversations`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON() as (typeof bodies)[number];
    bodies.push(body);
    followedUp = Boolean(body.follow_up_to);
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: body.follow_up_to ? "run-follow" : "run-success", status: "running" }),
    });
  });
  return bodies;
}

test("a finished answer offers a follow-up, and asking it continues the same conversation", async ({ page }) => {
  const bodies = await mockFollowUpFlow(page);
  await page.goto(`/?run=${ANSWERED.id}`);

  const box = page.getByLabel("Follow-up", { exact: true });
  await expect(box.getByText(/Still about\s*Margaret Ellison/)).toBeVisible();
  await box.getByLabel("Ask a follow-up").fill(FOLLOW_UP_QUESTION);
  await box.getByRole("button", { name: "Ask follow-up" }).click();

  await expect(page).toHaveURL(/run=run-follow/);
  // The request names the run it continues; the server keeps the patient, so none is sent.
  expect(bodies.at(-1)?.follow_up_to).toBe("run-success");
  expect(bodies.at(-1)?.patient_id ?? null).toBeNull();

  // Two turns: the first is folded away, the new one is live.
  await expect(page.getByText("Conversation · 2 questions")).toBeVisible();
  await expect(page.getByRole("group").filter({ hasText: "What is an A1c test?" })).toBeVisible();
  await expect(page.getByLabel("Outcome", { exact: true }).getByText("Published to you")).toBeVisible();
});

test("a rewritten follow-up shows how it was understood", async ({ page }) => {
  await mockFollowUpFlow(page);
  await page.goto(`/?run=${FOLLOW_UP.id}`);

  const summary = page.getByLabel("Run summary", { exact: true });
  await expect(summary).toContainText(FOLLOW_UP_QUESTION);
  await expect(summary).toContainText(`Understood as “${REWRITE}”`);
  await expect(page.getByLabel("Trace", { exact: true })).toContainText(`Understood as: “${REWRITE}”`);
});

test("an earlier turn unfolds to show its answer and can be reopened in full", async ({ page }) => {
  await mockFollowUpFlow(page);
  await page.goto(`/?run=${FOLLOW_UP.id}`);

  const earlier = page.getByRole("group").filter({ hasText: "What is an A1c test?" });
  await earlier.locator("summary").click();
  await expect(earlier.getByText(/Your most recent HbA1c was 7\.2%/)).toBeVisible();

  await earlier.getByRole("button", { name: /See how it was checked/ }).click();
  await expect(page).toHaveURL(/run=run-success/);
});

test("a refused follow-up shows the reason and keeps the conversation", async ({ page }) => {
  await mockRuns(page, [ANSWERED]);
  await page.route(`${API}/conversations`, (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({ detail: "This conversation has reached its limit of 8 questions. Start a new one." }),
        })
      : route.fallback()
  );
  await page.goto(`/?run=${ANSWERED.id}`);

  const box = page.getByLabel("Follow-up", { exact: true });
  await box.getByLabel("Ask a follow-up").fill("one more?");
  await box.getByRole("button", { name: "Ask follow-up" }).click();

  await expect(box.getByRole("alert")).toContainText("reached its limit of 8 questions");
  await expect(page).toHaveURL(/run=run-success/);
});

test("starting a new conversation clears the thread", async ({ page }) => {
  await mockRuns(page, [ANSWERED]);
  await page.goto(`/?run=${ANSWERED.id}`);

  await page.getByRole("button", { name: "Start a new conversation" }).click();

  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByLabel("Follow-up", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Run summary", { exact: true })).toHaveCount(0);
});

test("there is no follow-up box while an answer is still being produced", async ({ page }) => {
  // An event stream that never ends keeps the run "running".
  await mockRuns(page, [ANSWERED]);
  await page.route(`${API}/conversations/${ANSWERED.id}/events`, () => new Promise(() => undefined));
  await page.goto(`/?run=${ANSWERED.id}`);

  await expect(page.getByLabel("Run summary", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Follow-up", { exact: true })).toHaveCount(0);
});

test("showing a conversation does not poll the server in a loop", async ({ page }) => {
  await mockRuns(page, [ANSWERED]);
  let threadRequests = 0;
  page.on("request", (r) => r.url().endsWith("/thread") && (threadRequests += 1));

  await page.goto(`/?run=${ANSWERED.id}`);
  await expect(page.getByLabel("Follow-up", { exact: true })).toBeVisible();
  await page.waitForTimeout(2000);

  // One read to show the thread and one refresh when the run finishes; never a stream of them.
  expect(threadRequests).toBeLessThanOrEqual(4);
});
