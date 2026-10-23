import { expect, test } from "@playwright/test";
import { browserTestPorts } from "./ports";

const consoleBaseUrl = `http://127.0.0.1:${browserTestPorts.console}`;

test("the staff dashboard remains preview-only and returns focus after navigation", async ({
  page,
  request,
}) => {
  await page.goto(consoleBaseUrl);

  const main = page.locator("#staff-main");
  await expect(page.getByText("Preview only · no authenticated staff session")).toBeVisible();
  await expect(main).toContainText("This screen is not connected to an authenticated staff session.");

  const commandTrigger = page.getByRole("button", { name: "Search console destinations" });
  await commandTrigger.click();
  const commandInput = page.getByRole("textbox", { name: "Search preview navigation" });
  await expect(commandInput).toBeFocused();
  await expect
    .poll(
      () => commandInput.evaluate((element) => Number.parseFloat(getComputedStyle(element).outlineWidth)),
      { timeout: 5_000 },
    )
    .toBeGreaterThanOrEqual(2);
  const commandFocusStyle = await commandInput.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      focusVisible: element.matches(":focus-visible"),
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth),
    };
  });
  expect(commandFocusStyle.focusVisible).toBeTruthy();
  expect(commandFocusStyle.outlineStyle).not.toBe("none");
  expect(commandFocusStyle.outlineWidth).toBeGreaterThanOrEqual(2);
  await page.keyboard.press("Escape");
  await expect(commandTrigger).toBeFocused();

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(main.getByRole("heading", { name: "Analytics & CX Scorecard" })).toBeVisible();
  await expect(main).toBeFocused();

  const deniedScorecard = await request.get(`${consoleBaseUrl}/api/scorecard`);
  expect(deniedScorecard.status()).toBe(403);
  expect(deniedScorecard.headers()["cache-control"]).toContain("no-store");
  await expect(deniedScorecard.json()).resolves.toEqual({
    error: "AUTHENTICATED_STAFF_SESSION_REQUIRED",
  });
});

test("the staff dashboard mobile rail returns focus after Escape", async ({ page }) => {
  await page.setViewportSize({ height: 720, width: 320 });
  await page.goto(consoleBaseUrl);

  const mobileNav = page.locator("#mobile-ops-nav-btn");
  await mobileNav.click();
  await expect(mobileNav).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#staff-rail")).not.toHaveAttribute("inert", "");
  await expect(page.locator("#staff-rail-groups a").first()).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(mobileNav).toHaveAttribute("aria-expanded", "false");
  await expect(mobileNav).toBeFocused();
});
