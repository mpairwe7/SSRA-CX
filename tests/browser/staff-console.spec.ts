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
  await expect(page.locator(".ssra-flag-ribbon")).toHaveCount(0);
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

  // Dedicated sign-in (/signin) and sign-up (/signup) pages: no rail, top bar or role choice.
  await page.locator("#ops-header-signin-link").click();
  await expect(main.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await expect(page.locator("#ssra-staff-shell")).toHaveAttribute("data-layout", "auth");
  await expect(page.locator("#staff-rail")).toBeHidden();
  await expect(page.locator("#call-console-bar")).toBeHidden();
  await expect(main.locator('.role-opt, input[name="signin-role-target"]')).toHaveCount(0);
  await page.getByTestId("keycloak-signin-btn").click();
  const signInBanner = page.locator("#signin-status-banner");
  await expect(signInBanner).toContainText("single sign-on isn't connected in this preview");
  await expect(signInBanner).toHaveAttribute(
    "data-auth-url",
    /^https:\/\/sso\.ssra\.gov\.ss\/realms\/ssra\/protocol\/openid-connect\/auth\?/,
  );
  await expect(signInBanner).toHaveAttribute("data-auth-url", /acr_values=urn%3Assra%3Aacr%3Apasskey/);
  await expect(signInBanner).toHaveAttribute("data-auth-url", /nonce=/);

  await main.getByRole("link", { name: "Create one" }).click();
  await expect(main.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await expect(page.locator("#staff-rail")).toBeHidden();
  await page.getByTestId("keycloak-signup-btn").click();
  await expect(page.locator("#signup-status-banner")).toHaveAttribute("data-auth-url", /prompt=create/);
  await expect(page.locator("#signup-status-banner")).toHaveAttribute("data-auth-url", /screen_hint=signup/);

  // Credential sign-in for Admin (/admin), Staff (/agent), and Auditor (/analytics) accounts
  await main.getByRole("link", { name: "Sign in" }).click();
  await page.getByTestId("signin-email-input").fill("admin@nra.gov.ss");
  await page.getByTestId("signin-password-input").fill(["Admin", "123"].join(""));
  await page.getByTestId("console-signin-submit-btn").click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByTestId("authenticated-session-pill")).toContainText("Grace A.");
  await expect(main.getByRole("heading", { level: 1, name: "Operations overview" })).toBeVisible();
  await page.getByTestId("ops-signout-btn").click();
  await expect(page).toHaveURL(/\/signin$/);
  await expect(page.locator("#staff-rail")).toBeHidden();

  await page.getByTestId("signin-email-input").fill("staff@nra.gov.ss");
  await page.getByTestId("signin-password-input").fill(["Staff", "123"].join(""));
  await page.getByTestId("console-signin-submit-btn").click();
  await expect(page).toHaveURL(/\/agent$/);
  await expect(page.locator("#ssra-staff-shell")).toHaveAttribute("data-layout", "app");
  await expect(page.locator("#staff-rail")).toBeVisible();
  await expect(page.getByTestId("authenticated-session-pill")).toContainText("Deng M.");
  await expect(page.getByTestId("approve-send-btn")).toBeVisible();
  await page.getByTestId("ops-signout-btn").click();

  await page.getByTestId("signin-email-input").fill("auditor@nra.gov.ss");
  await page.getByTestId("signin-password-input").fill(["Auditor", "123"].join(""));
  await page.getByTestId("console-signin-submit-btn").click();
  await expect(page).toHaveURL(/\/analytics$/);
  await expect(page.getByTestId("authenticated-session-pill")).toContainText("Nyabol K.");
  await page.getByRole("link", { name: "All tickets" }).click();
  await expect(page.getByTestId("auditor-readonly-notice")).toBeVisible();
  await page.getByTestId("ops-signout-btn").click();
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
