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
  const commandInput = page.getByRole("combobox", { name: "Search preview navigation" });
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
  await expect(page.locator("#preview-eyebrow")).toContainText("Observe · Preview only");
  await expect(main.locator(".ops-stat-grid.ov-stats .ops-stat")).toHaveCount(4);
  await expect(main).toBeFocused();

  const deniedScorecard = await request.get(`${consoleBaseUrl}/api/scorecard`);
  expect(deniedScorecard.status()).toBe(403);
  expect(deniedScorecard.headers()["cache-control"]).toContain("no-store");
  await expect(deniedScorecard.json()).resolves.toEqual({
    error: "AUTHENTICATED_STAFF_SESSION_REQUIRED",
  });

  const deniedAuditApi = await request.get(`${consoleBaseUrl}/v1/admin/audit-verify`);
  expect(deniedAuditApi.status()).toBe(403);

  // Switching preview persona to Tax agent while on /analytics redirects to /agent (My queue & Copilot)
  await page.locator("#staff-acct-trigger").click();
  await page.getByRole("menuitemradio", { name: "Tax agent view (preview)" }).click();
  await expect(main.getByRole("heading", { name: "My queue & Copilot" })).toBeVisible();
  await expect(page.locator("#acct-display-name")).toHaveText("Tax agent preview");
  await expect(page.locator("#acct-initials")).toHaveText("ST");
  await expect(page.locator("#spec-standard")).toContainText("OWASP ASI03");

  // Sign-in (/signin), Sign-up (/signup), and Callback (/signin/callback) Keycloak 26 OIDC + Passkey flows
  await page.locator("#ops-header-signin-link").click();
  await expect(main.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await expect(main.locator(".role-opt.active")).toHaveCount(1);
  await expect(main.locator('[data-role-card="ssra_staff"]')).toHaveClass(/active/);
  await page.getByTestId("keycloak-signin-btn").click();
  await expect(page.locator("#signin-status-banner")).toContainText(
    "https://sso.ssra.gov.ss/realms/ssra/protocol/openid-connect/auth",
  );
  await expect(page.locator("#signin-status-banner")).toContainText(
    "acr_values=urn%3Assra%3Aacr%3Apasskey",
  );
  await expect(page.locator("#signin-status-banner")).toContainText("nonce=");

  await page.getByTestId("signin-different-account").click();
  await expect(page.locator("#signin-status-banner")).toContainText("prompt=login");

  await main.getByRole("link", { name: "Create one" }).click();
  await expect(main.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await page.getByTestId("keycloak-signup-btn").click();
  await expect(page.locator("#signup-status-banner")).toContainText("prompt=create");
  await expect(page.locator("#signup-status-banner")).toContainText("screen_hint=signup");
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
