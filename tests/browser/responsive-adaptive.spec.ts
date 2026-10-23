import { expect, test, type Page } from "@playwright/test";
import { browserTestPorts } from "./ports";

const consoleBaseUrl = `http://127.0.0.1:${browserTestPorts.console}`;
const SPACING_CSS =
  "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }";

// Synthetic, device-local conversation; no tax facts.
async function seedConversation(page: Page, turns: number): Promise<void> {
  await page.evaluate((n) => {
    const t: Array<Record<string, unknown>> = [];
    for (let i = 0; i < n; i++) {
      t.push({ role: "user", content: `Synthetic question ${i}` });
      t.push({
        role: "assistant",
        content: `Synthetic answer ${i}. ${"Synthetic sentence. ".repeat(6)}`,
        meta: { tier: "T0", kind: "answer", citations: [] },
      });
    }
    localStorage.setItem(
      "ssra-chat-store-v2",
      JSON.stringify({
        conversations: [
          { id: `thr_web_${"c".repeat(32)}`, title: "Synthetic saved conversation", isAuthenticated: false, updatedAtMs: Date.now(), turns: t },
        ],
      }),
    );
  }, turns);
}

async function openSeededConversation(page: Page): Promise<void> {
  await page.reload();
  if (await page.locator("#header-rail-btn").isVisible()) {
    if ((await page.locator("#header-rail-btn").getAttribute("aria-expanded")) !== "true") {
      await page.locator("#header-rail-btn").click();
    }
  }
  await page.locator("#rail-conv-list .rail-item").first().click();
}

// Controls that sit outside the viewport cannot be reached when the page itself does not scroll.
async function offscreenControls(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    return Array.from(document.querySelectorAll("button, a[href], select, textarea, input"))
      .filter((el) => {
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && !el.closest("[inert]") && (box.right > vw + 1 || box.left < -1);
      })
      .map((el) => el.id || el.className.toString());
  });
}

test("saved conversations appear as soon as the page loads", async ({ page }) => {
  await page.goto("/en");
  await seedConversation(page, 1);
  await page.reload();
  await expect(page.locator("#rail-conv-list .rail-item")).toHaveText(/Synthetic saved conversation/);
});

for (const [width, height] of [[320, 568], [360, 740], [568, 320]] as const) {
  test(`every control stays reachable at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ height, width });
    await page.goto("/en");
    expect(await offscreenControls(page)).toEqual([]);
    await expect(page.locator("#locale-select")).toBeInViewport();
  });
}

test("controls stay reachable with 200% text and WCAG text spacing", async ({ browser }) => {
  // bypassCSP stands in for a user stylesheet or extension, which page CSP does not govern.
  const context = await browser.newContext({ bypassCSP: true, viewport: { height: 740, width: 360 } });
  const page = await context.newPage();
  try {
    await page.goto("/en");
    await page.evaluate(() => {
      document.documentElement.style.fontSize = "200%";
    });
    expect(await offscreenControls(page)).toEqual([]);
    const chipOverflow = await page.locator(".landing-chip-text").evaluateAll((els) => els.filter((el) => el.scrollWidth > el.clientWidth + 1).length);
    expect(chipOverflow).toBe(0);
    await page.evaluate(() => {
      document.documentElement.style.fontSize = "";
    });
    await page.addStyleTag({ content: SPACING_CSS });
    expect(await offscreenControls(page)).toEqual([]);
  } finally {
    await context.close();
  }
});

test("the phone header stays compact and leaves room for the conversation", async ({ page }) => {
  await page.setViewportSize({ height: 568, width: 320 });
  await page.goto("/en");
  await seedConversation(page, 4);
  await openSeededConversation(page);
  const header = await page.locator(".chat-header").boundingBox();
  const messages = await page.locator("#ssra-chat-messages").boundingBox();
  expect(header?.height ?? 999).toBeLessThanOrEqual(120);
  expect((messages?.height ?? 0) / 568).toBeGreaterThanOrEqual(0.4);
  await expect(page.getByRole("button", { name: "Open voice input options" })).toBeInViewport();
});

test("short landscape screens scroll the whole column instead of a tiny transcript", async ({ page }) => {
  await page.setViewportSize({ height: 320, width: 568 });
  await page.goto("/en");
  await seedConversation(page, 4);
  await openSeededConversation(page);
  const layout = await page.evaluate(() => {
    const column = document.querySelector(".app-main-col") as HTMLElement;
    const list = document.getElementById("ssra-chat-messages") as HTMLElement;
    return { columnScrolls: column.scrollHeight > column.clientHeight, listIsNestedScroller: list.scrollHeight > list.clientHeight + 1 };
  });
  expect(layout).toEqual({ columnScrolls: true, listIsNestedScroller: false });
  await expect(page.locator("article.message-row-assistant").last()).toBeInViewport();
});

test("the viewport adapts to the on-screen keyboard and the browser UI follows the theme", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /interactive-widget=resizes-content/);
  await page.locator("#theme-toggle-btn").click();
  const theme = await page.locator("html").getAttribute("data-theme");
  const colors = await page.locator('meta[name="theme-color"]').evaluateAll((metas) => metas.map((m) => m.getAttribute("content")));
  const expected = theme === "dark" ? "#091310" : theme === "light" ? "#F6F7F2" : "#000000";
  expect(colors.every((c) => c === expected)).toBeTruthy();
});

test("the staff mobile menu button's accessible name includes its visible label", async ({ page }) => {
  await page.setViewportSize({ height: 720, width: 360 });
  await page.goto(consoleBaseUrl);
  await expect(page.getByRole("button", { exact: true, name: "Menu" })).toBeVisible();
});
