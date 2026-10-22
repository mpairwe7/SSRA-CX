import { expect, test } from "@playwright/test";

const consoleBaseUrl = "http://127.0.0.1:3102";

test("the staff dashboard remains preview-only and returns focus after navigation", async ({
  page,
  request,
}) => {
  await page.goto(consoleBaseUrl);

  const main = page.locator("#staff-main");
  await expect(page.getByText("Preview only · no authenticated staff session")).toBeVisible();
  await expect(main).toContainText("This screen is not connected to an authenticated staff session.");

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
