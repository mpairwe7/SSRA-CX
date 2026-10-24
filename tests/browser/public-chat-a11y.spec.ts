import { expect, test, type Page } from "@playwright/test";

// Replies come from the synthetic runtime; these tests check interaction semantics only.
async function ask(page: Page, message: string): Promise<void> {
  const replies = page.locator("article.message-row-assistant:not([aria-busy])");
  const before = await replies.count();
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill(message);
  await composer.press("Enter");
  await expect(replies).toHaveCount(before + 1, { timeout: 20_000 });
}

function relativeLuminance(rgb: readonly number[]): number {
  const [r = 0, g = 0, b = 0] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.040_45 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

test("replies are announced through a status region, not the transcript", async ({ page }) => {
  await page.goto("/en");
  const log = page.locator("#ssra-chat-messages");
  await expect(log).not.toHaveAttribute("aria-live", /.+/);
  await expect(log).not.toHaveAttribute("role", "log");
  await ask(page, "Synthetic public guidance question");
  await expect(page.locator("#chat-announcer")).toHaveText(/^Answer received\. Synthetic browser verification response\./);
  await ask(page, "synthetic-scenario:unavailable");
  await expect(page.locator("#chat-announcer")).toHaveText(/^Not answered\. SSRA Assist isn’t available right now/);
});

test("the composer status stays visible on a phone", async ({ page }) => {
  await page.setViewportSize({ height: 740, width: 360 });
  await page.goto("/en");
  await ask(page, "synthetic-scenario:unavailable");
  await expect(page.locator("#composer-hint")).toBeVisible();
  await expect(page.locator("#composer-hint")).toHaveText("Not answered. Your message is back in the box.");
});

test("the account panel is a disclosure that Escape closes", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator('[role="menu"], [role="menuitem"]')).toHaveCount(0);
  const trigger = page.locator("#acct-rail-trigger");
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("link", { name: /Open official e-Tax portal/ }).focus();
  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(trigger).toBeFocused();
  await expect(page.locator("#acct-popover")).toBeHidden();
});

test("settings tabs follow the APG keyboard model", async ({ page }) => {
  await page.goto("/en");
  await page.locator("#acct-rail-trigger").click();
  await page.getByRole("button", { name: /Settings & Privacy/ }).click();
  const general = page.getByRole("tab", { name: "General & Theme" });
  await expect(general).toBeFocused();
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("inert", "");

  await page.keyboard.press("ArrowDown");
  const voice = page.getByRole("tab", { name: "Voice & Speech" });
  await expect(voice).toBeFocused();
  await expect(voice).toHaveAttribute("aria-selected", "true");
  await expect(voice).toHaveAttribute("tabindex", "0");
  await expect(general).toHaveAttribute("tabindex", "-1");
  await expect(page.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "settings-tab-voice");

  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Privacy & Erasure" })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(general).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(page.locator("#ssra-app-shell")).not.toHaveAttribute("inert", "");
  await expect(page.locator("#acct-rail-trigger")).toBeFocused();
});

test("rename, delete, and clear use in-page dialogs with a safe default", async ({ page }) => {
  let nativeDialogs = 0;
  page.on("dialog", (dialog) => {
    nativeDialogs += 1;
    void dialog.dismiss();
  });
  await page.goto("/en");
  await ask(page, "Synthetic public guidance question");

  const row = page.locator(".rail-row").first();
  await row.hover();
  await row.getByRole("button", { name: /Rename conversation/ }).click();
  const dialog = page.getByRole("dialog", { name: "Rename conversation" });
  await expect(dialog).toBeVisible();
  const nameField = dialog.getByRole("textbox", { name: "Conversation name" });
  await expect(nameField).toBeFocused();
  await nameField.fill("Synthetic renamed conversation");
  await dialog.getByRole("button", { name: "Save name" }).click();
  await expect(page.locator(".rail-item").first()).toContainText("Synthetic renamed conversation");

  await row.hover();
  await row.getByRole("button", { name: /Delete conversation/ }).click();
  const confirm = page.getByRole("dialog", { name: "Delete this conversation?" });
  await expect(confirm.getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(".rail-row")).toHaveCount(1);

  await page.locator("#acct-rail-trigger").click();
  await page.getByRole("button", { name: /Settings & Privacy/ }).click();
  await page.getByRole("tab", { name: "Privacy & Erasure" }).click();
  await page.getByRole("button", { name: /Clear saved conversations on this device/ }).click();
  const clearAll = page.getByRole("dialog", { name: "Delete all saved conversations?" });
  await expect(clearAll).toBeVisible();
  await clearAll.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: /Clear saved conversations on this device/ })).toBeFocused();
  await page.getByRole("button", { name: /Clear saved conversations on this device/ }).click();
  await clearAll.getByRole("button", { name: "Delete all" }).click();
  await expect(page.locator(".rail-row")).toHaveCount(0);

  expect(nativeDialogs).toBe(0);
});

test("the page advertises only shortcuts that work", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("body")).not.toContainText(/Ctrl\+N|Ctrl\+,/);
  await ask(page, "Synthetic public guidance question");
  await page.getByRole("button", { name: /New Conversation/ }).click();
  await expect(page.locator("#landing-view")).toBeVisible();
  await page.keyboard.press("Control+k");
  const searchInput = page.getByRole("textbox", { name: "Search saved conversations" });
  await expect(searchInput).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#chat-view")).toBeVisible();
});

test("the offline status meets 4.5:1 contrast in the light theme", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();
  try {
    await page.goto("/en");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await context.setOffline(true);
    const badge = page.locator("#net-status-badge");
    await expect(badge).toHaveAttribute("data-connection", "offline");
    const colors = await badge.evaluate((el) => {
      const parse = (value: string) => (value.match(/[\d.]+/g) ?? []).map(Number);
      const hex = getComputedStyle(document.documentElement).getPropertyValue("--bg-0").trim();
      const page = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16));
      return { bg: parse(getComputedStyle(el).backgroundColor), fg: parse(getComputedStyle(el).color), page };
    });
    const alpha = colors.bg[3] ?? 1;
    const effectiveBg = [0, 1, 2].map((i) => (colors.bg[i] ?? 0) * alpha + (colors.page[i] ?? 255) * (1 - alpha));
    const [light, dark] = [relativeLuminance(colors.fg), relativeLuminance(effectiveBg)].sort((a, b) => b - a);
    expect(((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05)).toBeGreaterThanOrEqual(4.5);
  } finally {
    await context.setOffline(false);
    await context.close();
  }
});

test("Listen speaks in the interface language", async ({ page }) => {
  await page.addInitScript(() => {
    const spoken: string[] = [];
    Object.defineProperty(window, "__spokenLangs", { value: spoken });
    window.speechSynthesis.speak = (utterance: SpeechSynthesisUtterance) => {
      spoken.push(utterance.lang);
    };
  });
  await page.goto("/ar");
  await ask(page, "Synthetic public guidance question");
  await page.locator("article.message-row-assistant").last().getByRole("button", { name: /Listen/ }).click();
  expect(await page.evaluate(() => (window as unknown as { __spokenLangs: string[] }).__spokenLangs)).toEqual(["ar"]);
});

test("the theme follows the system until the user chooses one", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/en");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.reload();
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(html).toHaveAttribute("data-theme", "dark");

  await page.locator("#theme-toggle-btn").click();
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "light");
});

test("continuous voice conversation auto-advances across turns and filters speaker echo", async ({ page }) => {
  await page.addInitScript(() => {
    const startCalls: string[] = [];
    let currentRec: {
      lang: string;
      onresult: ((ev: unknown) => void) | null;
      onend: (() => void) | null;
      stop: () => void;
    } | null = null;

    class MockSpeechRecognition {
      lang = "en-US";
      continuous = false;
      interimResults = false;
      onresult: ((ev: unknown) => void) | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        startCalls.push(this.lang);
        currentRec = this;
      }
      stop() {
        if (currentRec === this) currentRec = null;
      }
    }

    Object.defineProperty(window, "SpeechRecognition", {
      value: MockSpeechRecognition,
      configurable: true,
    });
    Object.defineProperty(window, "__voiceTest", {
      value: {
        getStartCalls: () => startCalls.slice(),
        emitTranscript: (text: string) => {
          const rec = currentRec;
          rec?.onresult?.({ results: [[{ transcript: text }]] });
          rec?.onend?.();
          if (currentRec === rec) currentRec = null;
        },
      },
    });
    window.speechSynthesis.speak = (utterance: SpeechSynthesisUtterance) => {
      utterance.onstart?.(new Event("start") as SpeechSynthesisEvent);
      window.setTimeout(() => {
        utterance.onend?.(new Event("end") as SpeechSynthesisEvent);
      }, 20);
    };
  });

  await page.goto("/en");
  await page.locator("#open-call-btn").click();
  await expect(page.locator("#call-lang-chip-text")).toHaveText("English · auto");
  await page.locator("#call-lang-chip").click();
  await page.locator('.call-lang-option[data-call-lang="en"]').click();
  await expect(page.locator("#call-lang-chip-text")).toHaveText("English · chosen");

  const listenBtn = page.locator("#call-listen-btn");
  await listenBtn.click();
  await expect(listenBtn).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#call-orb")).toHaveAttribute("data-mode", "listening");
  await expect(page.locator("#composer-recording-bar")).toBeVisible();

  // Turn 1: spoken question is sent automatically, spoken back, and recognition re-arms after cooldown.
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitTranscript: (t: string) => void } }).__voiceTest.emitTranscript(
      "Where can I find general e-Tax filing guidance?",
    );
  });
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(1);
  await expect(page.locator("#call-thread .call-turn--caller")).toHaveCount(1);
  await expect(page.locator("#call-thread .call-turn--agent")).toHaveCount(1);
  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window as unknown as { __voiceTest: { getStartCalls: () => string[] } }).__voiceTest.getStartCalls().length,
        ),
      { timeout: 5_000 },
    )
    .toBeGreaterThanOrEqual(2);

  // Speaker echo matching the assistant's reply is ignored and does not create a second turn.
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitTranscript: (t: string) => void } }).__voiceTest.emitTranscript(
      "Synthetic browser verification response",
    );
  });
  await expect(page.locator("#call-voice-status")).toContainText("Ignored speaker echo");
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(1);

  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window as unknown as { __voiceTest: { getStartCalls: () => string[] } }).__voiceTest.getStartCalls().length,
        ),
      { timeout: 5_000 },
    )
    .toBeGreaterThanOrEqual(3);

  // Turn 2: a genuine follow-up question succeeds without re-clicking the microphone button.
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitTranscript: (t: string) => void } }).__voiceTest.emitTranscript(
      "What is the PAYE filing deadline each month?",
    );
  });
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(2);

  // Officer handoff -> Request a callback instead -> End call (CallScreen.tsx dock flows).
  const officerBtn = page.locator("#call-officer-btn");
  await expect(officerBtn).toHaveAttribute("aria-label", "Request an SSRA officer");
  await officerBtn.click();
  await expect(page.locator("#call-status-pill")).toHaveAttribute("data-status", "transferring");
  await expect(officerBtn).toHaveAttribute("aria-label", "Request a callback instead");
  await officerBtn.click();
  await expect(page.locator("#call-status-pill")).toHaveAttribute("data-status", "ended");
  await expect(officerBtn).toHaveAttribute("aria-label", "Request an SSRA officer");

  await page.locator("#call-hangup-btn").click();
  await expect(page.locator("#call-status-pill")).toHaveAttribute("data-status", "ended");
  await expect(page.locator("#call-listen-btn")).toHaveAttribute("aria-pressed", "false");
  await page.locator("#close-call-btn").click();

  // Main chat composer voice mode button couples with auto-narrate and Escape cancels recording (useVoiceEscape).
  const voiceModeBtn = page.locator("#composer-voicemode-btn");
  await voiceModeBtn.click();
  await expect(voiceModeBtn).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#composer-recording-bar")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(voiceModeBtn).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("#composer-recording-bar")).toBeHidden();

  // Composer '+' attachment menu -> file attachment -> DocumentInspectionModal (OQ-017 truthful state) -> suggested prompt -> remove.
  await page.locator("#composer-add-btn").click();
  await expect(page.locator("#addmenu-modal-backdrop")).toHaveClass(/open/);
  await page.keyboard.press("Escape");
  await page.locator("#composer-file-input").setInputFiles({
    name: "etax_portal_screenshot.png",
    mimeType: "image/png",
    buffer: Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
  });
  const chip = page.locator('[data-testid="attachment-chip"]');
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("SSRA e-Tax Portal Screenshot");

  await chip.locator("[data-inspect-att]").click();
  await expect(page.locator("#doc-inspect-modal-backdrop")).toHaveClass(/open/);
  await expect(page.locator("#doc-modal-title")).toHaveText("etax_portal_screenshot.png");
  await expect(page.locator("#doc-modal-oq017-note")).toContainText("OQ-017");
  await page.locator("#doc-modal-report-btn").click();
  await expect(page.locator("#composer-hint")).toContainText("Inspection receipt downloaded");
  await page.locator("#doc-modal-prompts [data-doc-prompt]").first().click();
  await expect(page.locator("#doc-inspect-modal-backdrop")).not.toHaveClass(/open/);
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(3);

  await chip.locator("[data-remove-att]").click();
  await expect(chip).toHaveCount(0);
});

