import { expect, test, type Locator, type Page } from "@playwright/test";

// Every reply comes from the synthetic scenarios in mock-runtime.mjs; none is a tax fact.
async function askScenario(page: Page, message: string): Promise<Locator> {
  const replies = page.locator("article.message-row-assistant:not([aria-busy])");
  const before = await replies.count();
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill(message);
  await composer.press("Enter");
  await expect(replies).toHaveCount(before + 1, { timeout: 20_000 });
  return replies.last();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/en");
});

test("public cards never fill missing values with invented facts", async ({ page }) => {
  const handoff = await askScenario(page, "synthetic-scenario:handoff-reason-only");
  await expect(handoff).toContainText("can’t confirm officer availability or contact hours");
  await expect(handoff).not.toContainText(/Duty Hours|08:00|Domestic Taxes Desk/);

  const personal = await askScenario(page, "synthetic-scenario:partial-personal-card");
  await expect(personal).toContainText("Secure sign-in needed");
  await expect(personal).not.toContainText(/COMPLIANT|Outstanding Balance/);

  const unregistered = await askScenario(page, "synthetic-scenario:unregistered-card");
  await expect(unregistered).toContainText("Synthetic scenario response.");
  await expect(unregistered).not.toContainText(/SYNTHETIC-REF|SyntheticUnregisteredCard|Cash-Free/i);
});

test("public chat offers no action confirmation it cannot perform", async ({ page }) => {
  const reply = await askScenario(page, "synthetic-scenario:pending-confirmation");
  await expect(reply).toContainText("Secure sign-in needed");
  await expect(reply.getByRole("button", { name: /Confirm/ })).toHaveCount(0);
  await expect(page.locator("[data-confirm-token]")).toHaveCount(0);
});

test("estimates render only with an approved source and an estimate label", async ({ page }) => {
  const cited = await askScenario(page, "synthetic-scenario:estimate-with-source");
  await expect(cited).toContainText("Estimate only. It is not an official assessment.");
  await expect(cited).toContainText("111");
  await expect(cited).toContainText("Synthetic Test Document · Synthetic-Section-1");
  await expect(cited).toContainText("effective from 2000-01-01");
  await expect(cited).toContainText("1 approved source");

  const uncited = await askScenario(page, "synthetic-scenario:estimate-without-source");
  await expect(uncited).toContainText("Estimate unavailable");
  await expect(uncited.locator(".gen-kv")).toHaveCount(0);
  await expect(uncited).toContainText("No source cited");

  const unregistered = await askScenario(page, "synthetic-scenario:unregistered-calculator-type");
  await expect(unregistered).toContainText("Synthetic scenario response.");
  await expect(unregistered.locator(".gen-ui-card")).toHaveCount(0);
  await expect(unregistered).not.toContainText("222");
});

test("answers show plain trust cues instead of internal telemetry", async ({ page }) => {
  const reply = await askScenario(page, "Synthetic public guidance question");
  await expect(reply).toContainText("No source cited");
  await expect(reply).not.toContainText(/Tier T0|synthetic_intent_slug|EQ:|Thought for|Provenance Verified/);
});

test("failed turns state what happened without raw error bodies", async ({ page }) => {
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  const cases: ReadonlyArray<readonly [string, RegExp]> = [
    ["synthetic-scenario:unavailable", /isn’t available right now, so your question wasn’t answered/],
    ["synthetic-scenario:rate-limited", /Wait 7 seconds, then try again/],
    ["synthetic-scenario:html-error", /Something went wrong at SSRA Assist/],
    ["synthetic-scenario:drop-connection", /didn’t reply in time, so your question may not have been answered/],
  ];
  for (const [message, expected] of cases) {
    const reply = await askScenario(page, message);
    await expect(reply).toContainText(expected);
    await expect(reply).toContainText("Not answered");
    await expect(reply).not.toContainText(/[{}]|Synthetic unavailable detail|BFF_TURN_PROXY_ERROR|connection dropped/);
    await expect(composer).toHaveValue(message);
    await composer.fill("");
  }

  const failed = page.locator("article.message-row-assistant").last();
  await failed.getByRole("button", { name: "Try again" }).click();
  await expect(page.locator("article.message-row-user")).toHaveCount(4);
  await expect(page.locator("article.message-row-assistant").last()).toContainText("didn’t reply in time");
});

test("copy reports failure truthfully and thread ids are unguessable", async ({ page, request }) => {
  const reply = await askScenario(page, "Synthetic public guidance question");
  await page.evaluate(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: () => Promise.reject(new Error("synthetic denial")) },
    });
  });
  await reply.getByRole("button", { name: "Copy" }).click();
  await expect(reply.getByRole("button", { name: "Copy failed" })).toBeVisible();

  const threadId = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ssra-chat-store-v2") ?? "{}").conversations?.[0]?.id,
  );
  expect(threadId).toMatch(/^thr_web_[0-9a-f]{32}$/);

  for (const body of [{ message: "x", thread_id: "../../synthetic" }, ["not-an-object"], null]) {
    const response = await request.post("/api/turns", { data: body });
    expect(response.status()).toBe(400);
  }
});

test("a reply still in progress is never saved to the device", async ({ page }) => {
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill("synthetic-scenario:slow");
  await composer.press("Enter");
  await expect(page.locator("article[aria-busy='true']")).toHaveCount(1);
  await page.locator("#theme-toggle-btn").click();
  const stored = await page.evaluate(() => localStorage.getItem("ssra-chat-store-v2") ?? "");
  expect(stored).not.toContain("Preparing an answer");
  expect(stored).not.toContain('"pending"');
});

test("assistant replies render structured paragraphs, ordered lists, callouts, and LTR-isolated links", async ({
  page,
}) => {
  const reply = await askScenario(page, "synthetic-scenario:structured-answer");
  const content = reply.locator(".turn-content-text");
  await expect(content.locator("ol.md-list.md-ol > li")).toHaveCount(3);
  await expect(content.locator("ol.md-list.md-ol > li").nth(1)).toHaveText("TIN search");
  await expect(content.locator("ol.md-list.md-ol > li").nth(2)).toHaveText("TCC verification.");
  await expect(content.locator("aside.md-callout.md-callout-note")).toContainText(
    "Keep your e-Tax receipt.",
  );
  await expect(content.locator('a.md-link[dir="ltr"][href="https://www.nra.gov.ss/tools"]')).toBeVisible();
  await expect(content.locator('a.md-link[dir="ltr"][href="mailto:support@nra.gov.ss"]')).toBeVisible();
  await expect(content.locator('a.md-link[dir="ltr"][href="tel:+211918806493"]')).toBeVisible();
});

