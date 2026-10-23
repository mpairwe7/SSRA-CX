import { expect, test, type Page } from "@playwright/test";
import { browserTestPorts } from "./ports";

const consoleBaseUrl = `http://127.0.0.1:${browserTestPorts.console}`;

// Synthetic, device-local conversation; no tax facts.
async function openSeededConversation(page: Page, turns: number): Promise<void> {
  await page.evaluate((n) => {
    const t: Array<Record<string, unknown>> = [];
    for (let i = 0; i < n; i++) {
      t.push({ role: "user", content: `Synthetic question ${i}` });
      t.push({ role: "assistant", content: `Synthetic answer ${i}.`, meta: { tier: "T0", kind: "answer", citations: [] } });
    }
    localStorage.setItem(
      "ssra-chat-store-v2",
      JSON.stringify({ conversations: [{ id: `thr_web_${"d".repeat(32)}`, title: "Synthetic", isAuthenticated: false, updatedAtMs: Date.now(), turns: t }] }),
    );
  }, turns);
  await page.reload();
  await page.locator("#rail-conv-list .rail-item").first().click();
}

test("a new reply updates the transcript without rebuilding earlier messages", async ({ page }) => {
  await page.goto("/en");
  await openSeededConversation(page, 3);
  await page.locator("article.message-row").first().evaluate((el) => {
    (el as HTMLElement & { syntheticMarker?: boolean }).syntheticMarker = true;
  });
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill("Synthetic public guidance question");
  await composer.press("Enter");
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(4);
  const kept = await page.locator("article.message-row").first().evaluate((el) => (el as HTMLElement & { syntheticMarker?: boolean }).syntheticMarker === true);
  expect(kept).toBeTruthy();
});

test("a long conversation opens with recent turns first and then completes in order", async ({ page }) => {
  await page.goto("/en");
  await openSeededConversation(page, 80);
  await expect(page.locator("article.message-row")).toHaveCount(160);
  // textContent, not innerText: content-visibility skips rendering of off-screen rows.
  const order = await page.locator("article.message-row-user .bubble").allTextContents();
  expect(order[0]).toBe("Synthetic question 0");
  expect(order.at(-1)).toBe("Synthetic question 79");
  await expect(page.locator("article.message-row").last()).toBeInViewport();
  expect(await page.locator("article.message-row").first().evaluate((el) => getComputedStyle(el).contentVisibility)).toBe("auto");
});

for (const [surface, url, policy] of [
  ["public chat", "/en", "ssra-web-html"],
  ["staff preview", consoleBaseUrl, "ssra-ops-html"],
] as const) {
  test(`${surface} enforces Trusted Types`, async ({ page }) => {
    const response = await page.goto(url);
    const csp = response?.headers()["content-security-policy"] ?? "";
    expect(csp).toContain("require-trusted-types-for 'script'");
    expect(csp).toContain(`trusted-types ${policy}`);
    const rejected = await page.evaluate(() => {
      try {
        document.createElement("div").innerHTML = "<b>synthetic</b>";
        return false;
      } catch (error) {
        return error instanceof TypeError;
      }
    });
    expect(rejected).toBeTruthy();
  });
}

test("the service worker still registers through its Trusted Types script-URL policy", async ({ page }) => {
  await page.goto("/en");
  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(scope).toMatch(/\/$/);
});
