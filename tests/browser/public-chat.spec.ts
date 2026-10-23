import { expect, test, type APIRequestContext } from "@playwright/test";
import { browserTestPorts } from "./ports";

const mockRuntimeUrl = `http://127.0.0.1:${browserTestPorts.runtime}`;

type CapturedRuntimeRequest = {
  readonly body: Record<string, unknown>;
  readonly headers: {
    readonly authorization: string | null;
    readonly subject_ref: string | null;
    readonly traceparent: string | null;
  };
};

async function resetRuntimeRequests(request: APIRequestContext): Promise<void> {
  const response = await request.delete(`${mockRuntimeUrl}/test/requests`);
  expect(response.status()).toBe(204);
}

async function getRuntimeRequests(
  request: APIRequestContext,
): Promise<CapturedRuntimeRequest[]> {
  const response = await request.get(`${mockRuntimeUrl}/test/requests`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as CapturedRuntimeRequest[];
}

test.beforeEach(async ({ request }) => {
  await resetRuntimeRequests(request);
});

test("public chat renders a safe answer through the subject-stripping BFF", async ({
  page,
  request,
}) => {
  await page.goto("/en");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByLabel("Conversation history and account")).toBeVisible();

  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await expect(composer).toBeVisible();
  await composer.fill("Synthetic public guidance question");
  await composer.press("Enter");
  await expect(
    page.locator("#ssra-chat-messages").getByText("Synthetic browser verification response."),
  ).toBeVisible();
  await expect(page.locator("#rail-conv-list .rail-item-dot")).toHaveCount(1);

  // Desktop Ctrl+B collapse & left-edge hover-peek (chatv2/shell.css pattern)
  await page.keyboard.press("Control+b");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-sidebar", "collapsed");
  await page.locator("#rail-hotzone").dispatchEvent("mouseenter");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-rail-peek", "true");
  await page.locator("#conversation-rail").dispatchEvent("mouseleave");
  await expect(page.locator("#ssra-app-shell")).not.toHaveAttribute("data-rail-peek", "true");
  await page.keyboard.press("Control+b");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-sidebar", "open");

  const [captured] = await getRuntimeRequests(request);
  expect(captured?.body).toMatchObject({
    auth_level: "ANONYMOUS",
    channel: "web",
    locale: "en",
    low_data_mode: false,
    message: "Synthetic public guidance question",
    subject_ref: null,
  });
  expect(Object.keys(captured?.body ?? {}).sort()).toEqual([
    "auth_level",
    "channel",
    "locale",
    "low_data_mode",
    "message",
    "subject_ref",
    "thread_id",
  ]);
  expect(captured?.headers.authorization).toBeNull();
  expect(captured?.headers.subject_ref).toBeNull();
  expect(captured?.headers.traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/);

  const forgedStatus = await page.evaluate(async () => {
    const response = await fetch("/api/turns", {
      method: "POST",
      headers: {
        Authorization: "Bearer synthetic-browser-assertion",
        "Content-Type": "application/json",
        "X-Subject-Ref": "synthetic-foreign-subject",
      },
      body: JSON.stringify({
        auth_level: "STAFF",
        message: "Synthetic forged-identity request",
        role: "admin",
        subject_ref: "synthetic-foreign-subject",
        thread_id: "synthetic-browser-thread",
      }),
    });
    return response.status;
  });
  expect(forgedStatus).toBe(200);

  const capturedRequests = await getRuntimeRequests(request);
  const forgedRequest = capturedRequests.at(-1);
  expect(forgedRequest?.body).toEqual({
    auth_level: "ANONYMOUS",
    channel: "web",
    locale: "en",
    low_data_mode: false,
    message: "Synthetic forged-identity request",
    subject_ref: null,
    thread_id: "synthetic-browser-thread",
  });
  expect(forgedRequest?.headers.authorization).toBeNull();
  expect(forgedRequest?.headers.subject_ref).toBeNull();

  const protectedRouteStatuses = await page.evaluate(async () => {
    const paths = [
      "/v1/admin/audit-verify",
      "/%76%31/admin/audit-verify",
      "/v1%2Fadmin%2Faudit-verify",
    ];
    return Promise.all(
      paths.map(async (path) => ({ path, status: (await fetch(path)).status })),
    );
  });
  expect(protectedRouteStatuses).toEqual([
    { path: "/v1/admin/audit-verify", status: 403 },
    { path: "/%76%31/admin/audit-verify", status: 403 },
    { path: "/v1%2Fadmin%2Faudit-verify", status: 400 },
  ]);
});

test("the mobile rail reflows, keeps usable targets, and restores keyboard focus", async ({ page }) => {
  await page.setViewportSize({ height: 720, width: 320 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/en");

  expect(
    await page.evaluate(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches),
  ).toBeTruthy();

  const viewportWidth = await page.locator("html").evaluate((element) => element.scrollWidth);
  expect(viewportWidth).toBeLessThanOrEqual(320);

  const railToggle = page.getByRole("button", { name: "Open conversations" });
  const initialTargetBox = await railToggle.boundingBox();
  expect(initialTargetBox?.width).toBeGreaterThanOrEqual(24);
  expect(initialTargetBox?.height).toBeGreaterThanOrEqual(24);

  const reducedMotionDurationMs = await page.locator("#conversation-rail").evaluate((element) => {
    const duration = getComputedStyle(element).transitionDuration.split(",")[0]?.trim() ?? "0s";
    return duration.endsWith("ms") ? Number.parseFloat(duration) : Number.parseFloat(duration) * 1_000;
  });
  expect(reducedMotionDurationMs).toBeLessThanOrEqual(1);

  await railToggle.click();
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-mobile-rail", "open");
  await expect(page.locator("#conversation-rail")).not.toHaveAttribute("inert", "");
  await expect(page.getByRole("button", { name: /New Conversation/ })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-mobile-rail", "closed");
  await expect(railToggle).toBeFocused();

  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  for (let tabCount = 0; tabCount < 32; tabCount += 1) {
    if (await composer.evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(composer).toBeFocused();
  await expect
    .poll(
      () => composer.evaluate((element) => getComputedStyle(element).boxShadow),
      { timeout: 5_000 },
    )
    .toContain("3px");
  const focusStyle = await composer.evaluate((element) => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return {
      bottom: box.bottom,
      focusVisible: element.matches(":focus-visible"),
      outlineStyle: style.outlineStyle,
    };
  });
  expect(focusStyle.bottom).toBeLessThanOrEqual(720);
  expect(focusStyle.focusVisible).toBeTruthy();
  expect(focusStyle.outlineStyle).not.toBe("none");

  await composer.focus();
  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await expect(composer).toBeFocused();
});

test("Arabic direction, low-data mode, and offline fallback remain explicit", async ({ browser }) => {
  const context = await browser.newContext({
    colorScheme: "light",
    locale: "ar",
    reducedMotion: "reduce",
    viewport: { height: 720, width: 320 },
  });
  const page = await context.newPage();
  try {
    await page.goto("/ar");
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

    await page.getByRole("button", { name: "Open conversations" }).click();
    const railBox = await page.locator("#conversation-rail").boundingBox();
    expect(railBox?.x).toBeGreaterThan(0);
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: "Open conversations" }).click();
    await page.locator("#acct-rail-trigger").click();
    await page.getByRole("button", { name: /Settings & Privacy/ }).click();
    const lowDataToggle = page.locator("#toggle-lowdata-btn");
    await expect(lowDataToggle).toBeVisible();
    await lowDataToggle.click();
    await expect(page.locator("#net-status-text")).toContainText("Low-data mode");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");

    await context.setOffline(true);
    const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
    await composer.fill("Can I calculate PAYE while offline?");
    await composer.press("Enter");
    await expect(
      page.getByText(/I can’t calculate or confirm tax figures while offline/),
    ).toBeVisible();
    await expect(composer).toHaveValue("Can I calculate PAYE while offline?");
  } finally {
    await context.setOffline(false);
    await context.close();
  }
});
