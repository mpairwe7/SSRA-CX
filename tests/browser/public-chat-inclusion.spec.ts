import { expect, test, type Page } from "@playwright/test";

async function ask(page: Page, message: string): Promise<void> {
  const replies = page.locator("article.message-row-assistant:not([aria-busy])");
  const before = await replies.count();
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill(message);
  await composer.press("Enter");
  await expect(replies).toHaveCount(before + 1, { timeout: 20_000 });
}

test("unreviewed locales show English interface text with an honest notice", async ({ page }) => {
  await page.goto("/din");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("#langsel-code")).toHaveText("DIN");
  const notice = page.locator("#locale-notice");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("Thuɔŋjäŋ Dinka (din) hasn’t been reviewed yet, so it is shown in English");
  await expect(page.locator(".landing-chip")).not.toContainText(["Waraga"]);
  await expect(page.getByRole("textbox", { name: "Ask SSRA Assist" })).not.toHaveAttribute("placeholder", /Dinka/);

  await page.locator("#langsel-btn").click();
  await expect(page.getByRole("dialog", { name: "Response language" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Thuɔŋjäŋ Dinka.*Not yet reviewed/i })).toHaveCount(1);
  await page.getByRole("radio", { name: /Arabic.*العربية/i }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("#langsel-code")).toHaveText("AR");
  await expect(page.locator("#lang-auto-badge")).toBeHidden();
  await expect(notice).toBeHidden();
});

test("the composer discloses AI use, accuracy limits, and identifier risk", async ({ page }) => {
  await page.goto("/en");
  const disclosure = page.locator(".composer-disclosure");
  await expect(disclosure).toBeVisible();
  await expect(disclosure).toHaveAttribute("lang", "en");
  await expect(disclosure).toContainText("automated AI assistant and can make mistakes");
  await expect(disclosure).toContainText("Don’t enter your TIN, phone number, or passwords");
  await expect(page.locator("#rail-device-note")).toContainText("saved on this device only");
  await expect(page.locator("#net-status-badge")).toBeHidden();
  await expect(page.locator("#active-conv-title")).toBeHidden();
});

test("people on shared devices can stop saving conversations", async ({ page }) => {
  await page.goto("/en");
  await page.locator("#acct-rail-trigger").click();
  await page.getByRole("button", { name: /Settings & Privacy/ }).click();
  await page.getByRole("tab", { name: "Privacy & Erasure" }).click();
  const toggle = page.getByRole("button", { name: /Save conversations on this device: ON/ });
  await toggle.click();
  await expect(page.getByRole("button", { name: /Save conversations on this device: OFF/ })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#rail-device-note")).toContainText("not saved");

  await ask(page, "Synthetic public guidance question");
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("ssra-chat-store-v2") ?? "{}"));
  expect(stored.saveHistory).toBe(false);
  expect(stored.conversations).toEqual([]);
  await page.reload();
  await expect(page.locator(".rail-row")).toHaveCount(0);
});

test("low-data mode removes blur, decorative backgrounds, and motion", async ({ page }) => {
  await page.goto("/en");
  const composerBox = page.locator(".composer-box");
  expect(await composerBox.evaluate((el) => getComputedStyle(el).backdropFilter)).not.toBe("none");
  await page.locator("#acct-rail-trigger").click();
  await page.getByRole("button", { name: /Settings & Privacy/ }).click();
  await page.locator("#toggle-lowdata-btn").click();
  await expect(page.locator("html")).toHaveAttribute("data-low-data", "true");
  expect(await composerBox.evaluate((el) => getComputedStyle(el).backdropFilter)).toBe("none");
  expect(
    await page.evaluate(() => getComputedStyle(document.body, "::before").backgroundImage),
  ).toBe("none");
});

test("without JavaScript the page points to the official portal", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  try {
    await page.goto("/en");
    await expect(page.locator(".noscript-note")).toBeVisible();
    await expect(page.locator(".noscript-note")).toContainText("https://etax.nra.gov.ss/");
  } finally {
    await context.close();
  }
});

test("health checks reveal no internal service addresses", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.ok()).toBeTruthy();
  expect(Object.keys(await response.json()).sort()).toEqual(["service", "status"]);
});
