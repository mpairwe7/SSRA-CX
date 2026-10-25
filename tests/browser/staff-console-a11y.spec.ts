import { expect, test } from "@playwright/test";
import { browserTestPorts } from "./ports";

const consoleBaseUrl = `http://127.0.0.1:${browserTestPorts.console}`;

function contrastRatio(fg: readonly number[], bg: readonly number[]): number {
  const luminance = (rgb: readonly number[]) => {
    const [r = 0, g = 0, b = 0] = rgb.map((v) => {
      const c = v / 255;
      return c <= 0.040_45 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [light, dark] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
}

test("the command palette follows the APG combobox pattern", async ({ page }) => {
  await page.goto(consoleBaseUrl);
  await page.getByRole("button", { name: "Search console destinations" }).click();
  const combobox = page.getByRole("combobox", { name: "Search preview navigation" });
  await expect(combobox).toBeFocused();
  await expect(combobox).toHaveAttribute("aria-expanded", "true");
  await expect(combobox).toHaveAttribute("aria-controls", "cmdk-list");
  await expect(combobox).toHaveAttribute("aria-activedescendant", "cmdk-opt-0");
  await expect(page.locator("#ssra-staff-shell")).toHaveAttribute("inert", "");

  await page.keyboard.press("ArrowDown");
  await expect(combobox).toHaveAttribute("aria-activedescendant", "cmdk-opt-1");
  await expect(page.locator("#cmdk-opt-1")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#cmdk-opt-0")).toHaveAttribute("aria-selected", "false");
  await page.keyboard.press("Home");
  await expect(combobox).toHaveAttribute("aria-activedescendant", "cmdk-opt-0");

  await combobox.fill("zzz-synthetic-no-match");
  await expect(combobox).not.toHaveAttribute("aria-activedescendant", /.+/);
  await expect(page.locator("#cmdk-count")).toHaveText("No matching destinations");

  await page.keyboard.press("Escape");
  await expect(page.locator("#ssra-staff-shell")).not.toHaveAttribute("inert", "");
});

test("the account menu supports arrow keys and Escape", async ({ page }) => {
  await page.goto(consoleBaseUrl);
  const trigger = page.locator("#staff-acct-trigger");
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  const items = page.locator('#staff-acct-menu [role^="menuitem"]');
  await expect(items.first()).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(items.nth(1)).toBeFocused();
  await page.keyboard.press("End");
  await expect(items.last()).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(trigger).toBeFocused();
});

test("preview labels are readable in the light theme and styled as a warning", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("ssra-ops-theme", "light"));
  await page.goto(consoleBaseUrl);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const sample = async (selector: string) =>
    page.locator(selector).first().evaluate((el) => {
      const parse = (value: string) => (value.match(/[\d.]+/g) ?? []).map(Number);
      const surface = el.closest(".ops-panel") ?? document.body;
      return { bg: parse(getComputedStyle(surface).backgroundColor), fg: parse(getComputedStyle(el).color) };
    });
  const chip = await sample(".ops-preview-chip");
  expect(contrastRatio(chip.fg, chip.bg.length >= 3 ? chip.bg : [255, 255, 255])).toBeGreaterThanOrEqual(4.5);

  const pillColor = await page.locator(".presence-pill").evaluate((el) => getComputedStyle(el).color);
  const goodInk = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--ops-good-ink").trim());
  const warnInk = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--ops-warn-ink").trim());
  const toRgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;
  expect(pillColor).toBe(toRgb(warnInk));
  expect(pillColor).not.toBe(toRgb(goodInk));
});

test("the preview state is rendered without JavaScript and claims no live capabilities", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  try {
    await page.goto(`${consoleBaseUrl}/analytics`);
    await expect(page.getByRole("heading", { level: 1, name: "Analytics & CX Scorecard" })).toBeVisible();
    await expect(page.locator("#staff-main")).toContainText("not connected to an authenticated staff session");
    await expect(page.locator("#spec-standard")).toContainText("OpenSLO v1");
    await expect(page.locator("#rail-group-observe")).toHaveText("Observe");
    await expect(page.locator('#staff-rail a[href="/analytics"]')).toHaveAttribute("aria-current", "page");
    await expect(page).toHaveTitle("SSRA Operations Console Preview — Analytics & CX Scorecard");
    const html = await page.content();
    expect(html).not.toMatch(/AI phone receptionist|served right now|Merkle seal proof|blurb/);
  } finally {
    await context.close();
  }
});

test("mobile drawer at 320px displays full labels and account metadata even when desktop railMode is hover", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem("ssra-ops-rail-mode", "hover");
  });
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto(`${consoleBaseUrl}/admin`);
  await page.locator("#mobile-ops-nav-btn").click();
  await expect(page.locator("#staff-rail")).toHaveClass(/is-drawer-open/);
  await expect(page.locator("#rail-group-work")).toBeVisible();
  await expect(page.locator('#staff-rail a[href="/admin"] .staff-rail-label')).toBeVisible();
  await expect(page.locator("#acct-display-name")).toBeVisible();
});
