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

test("Sign in and Register explain portal sign-in in an in-page dialog", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator('[role="menu"], [role="menuitem"]')).toHaveCount(0);
  const footer = page.getByRole("group", { name: "Your e-Tax account" });
  for (const [name, text] of [
    ["Sign in", "Sign in isn’t available in SSRA Assist yet"],
    ["Register", "To register for a TIN or an e-Tax account, use the official e-Tax portal"],
  ] as const) {
    const opener = footer.getByRole("button", { name });
    await opener.click();
    const dialog = page.getByRole("dialog", { name });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(text);
    await expect(dialog.getByRole("button", { name: "Open e-Tax portal" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(opener).toBeFocused();
  }
});

test("settings tabs follow the APG keyboard model", async ({ page }) => {
  await page.goto("/en");
  await page.getByRole("button", { name: "Settings & Privacy" }).click();
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
  await expect(page.locator("#open-settings-btn")).toBeFocused();
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

  await page.getByRole("button", { name: "Settings & Privacy" }).click();
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
  await expect(page.locator("#header-rail-btn")).toBeHidden();
  await page.keyboard.press("Control+b");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-sidebar", "collapsed");
  await expect(page.locator("#header-rail-btn")).toBeVisible();
  await page.keyboard.press("Control+b");
  await expect(page.locator("#ssra-app-shell")).toHaveAttribute("data-sidebar", "open");
  await expect(page.locator("#header-rail-btn")).toBeHidden();
  await page.keyboard.press("Control+k");
  const searchInput = page.getByRole("textbox", { name: "Search saved conversations" });
  await expect(searchInput).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#chat-view")).toBeVisible();
});

test("the landing centres the composer between the headline and three suggestions", async ({ page }) => {
  await page.goto("/en");
  const main = page.locator("#main-content");
  await expect(main).toHaveAttribute("data-view", "landing");
  const chips = page.getByRole("group", { name: "Suggested tax questions" }).getByRole("button");
  await expect(chips).toHaveCount(3);
  await expect(chips.first()).toHaveText("How do I register for a TIN step by step?");
  const [headline, composer, prompts] = await Promise.all(
    ["#landing-headline", "#ssra-chat-form", "#landing-prompts"].map((selector) => page.locator(selector).boundingBox()),
  );
  expect((headline?.y ?? 0) + (headline?.height ?? 0)).toBeLessThanOrEqual(composer?.y ?? 0);
  expect((composer?.y ?? 0) + (composer?.height ?? 0)).toBeLessThanOrEqual(prompts?.y ?? 0);
  // Keyboard order follows the visual order: add, input, dictate, voice mode, then the suggestions.
  await page.locator("#composer-add-btn").focus();
  for (const next of ["#ssra-chat-input", "#voice-dictate-btn", "#composer-voicemode-btn"]) {
    await page.keyboard.press("Tab");
    await expect(page.locator(next)).toBeFocused();
  }
  await page.keyboard.press("Tab");
  await expect(chips.first()).toBeFocused();
  await ask(page, "Synthetic public guidance question");
  await expect(main).toHaveAttribute("data-view", "chat");
  await expect(page.locator("#landing-prompts")).toBeHidden();
});

test("Ctrl+Shift+O starts a new conversation and the rail fades only where content scrolls under", async ({ page }) => {
  await page.setViewportSize({ height: 640, width: 1280 });
  await page.goto("/en");
  await page.evaluate(() => {
    const now = Date.now();
    const conversations = Array.from({ length: 30 }, (_, i) => ({
      id: `thr_web_${String(i).padStart(32, "a")}`,
      isAuthenticated: false,
      title: `Synthetic saved conversation ${i}`,
      turns: [
        { content: `Synthetic question ${i}`, role: "user" },
        { content: "Synthetic answer.", meta: { citations: [], kind: "answer", tier: "T0" }, role: "assistant" },
      ],
      updatedAtMs: now - i * 60_000,
    }));
    localStorage.setItem("ssra-chat-store-v2", JSON.stringify({ conversations }));
  });
  await page.reload();
  const list = page.locator("#rail-conv-list");
  await expect(list).not.toHaveAttribute("data-fade-top");
  await expect(list).toHaveAttribute("data-fade-bottom", "");
  await list.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(list).toHaveAttribute("data-fade-top", "");
  await expect(list).not.toHaveAttribute("data-fade-bottom");

  const main = page.locator("#main-content");
  const newChat = page.getByRole("button", { name: "New Conversation" });
  await expect(newChat).toHaveAttribute("aria-keyshortcuts", "Control+Shift+O");
  await page.locator("#rail-conv-list .rail-item").first().click();
  await expect(main).toHaveAttribute("data-view", "chat");
  await expect(newChat).not.toHaveClass(/is-current/);
  await page.keyboard.press("Control+Shift+O");
  await expect(main).toHaveAttribute("data-view", "landing");
  await expect(newChat).toHaveClass(/is-current/);
});

test("the header is lean and hovers stay neutral", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("#theme-toggle-btn")).toHaveCount(0);
  await expect(page.locator(".ssra-flag-ribbon")).toHaveCount(0);
  const kebab = page.locator("#header-kebab-btn");
  await kebab.hover();
  await expect.poll(() => kebab.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgba(15, 23, 42, 0.08)");

  // New Conversation is the current page on the landing; hovering it still lifts the pill (Gemini pattern).
  const newChat = page.getByRole("button", { name: "New Conversation" });
  await expect(newChat).toHaveClass(/is-current/);
  const resting = await newChat.evaluate((el) => getComputedStyle(el).backgroundColor);
  await newChat.hover();
  await expect.poll(() => newChat.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe(resting);
  await expect.poll(() => newChat.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgba(255, 255, 255, 0.12)");
});

test("the composer placeholder rotates only while idle", async ({ page }) => {
  await page.clock.install();
  await page.goto("/en");
  const input = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  const phrase = page.locator("#composer-placeholder-text");
  await expect(input).toHaveAttribute("placeholder", "Ask anything you need about taxes");
  await expect(phrase).toHaveText("Ask anything you need about taxes");
  await page.clock.runFor(5_500);
  await expect(phrase).toHaveText("Drag and drop a screenshot for guidance");
  await input.focus();
  await page.clock.runFor(11_000);
  await expect(phrase).toHaveText("Drag and drop a screenshot for guidance");
  await input.fill("Synthetic draft");
  await expect(phrase).toBeHidden();
});

test("reduced motion keeps a static composer placeholder", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/en");
  await expect(page.locator("#ssra-chat-form")).not.toHaveClass(/has-rotating-placeholder/);
  await expect(page.locator("#composer-placeholder")).toBeHidden();
  await expect(page.getByRole("textbox", { name: "Ask SSRA Assist" })).toHaveAttribute("placeholder", "Ask anything you need about taxes");
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
    await expect(page.locator("#chat-announcer")).toContainText("Offline");
    await context.setOffline(false);
    await expect(badge).toBeHidden();
    await expect(page.locator("#chat-announcer")).toHaveText("Online");
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

  await page.locator("#header-kebab-btn").click();
  await page.locator("#header-menu-theme-btn").click();
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
        emitInterimTranscript: (text: string) => {
          const rec = currentRec;
          const item = Object.assign([{ transcript: text }], { isFinal: false });
          rec?.onresult?.({ results: [item] });
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

  // In-Call Receptionist Controls Strip (CallScreen.tsx lines 393-498): Repeat last, Slower pace, and Type a question.
  await expect(page.locator("#call-repeat-btn")).toBeVisible();
  const paceBtn = page.locator("#call-pace-btn");
  await paceBtn.click();
  await expect(paceBtn).toHaveAttribute("aria-pressed", "true");
  await expect(paceBtn).toHaveText("Normal pace");
  // Wait for recognition to re-arm after Turn 2's 450ms post-TTS cooldown, then test spoken pace control
  await expect
    .poll(
      () =>
        page.evaluate(
          () => (window as unknown as { __voiceTest: { getStartCalls: () => string[] } }).__voiceTest.getStartCalls().length,
        ),
      { timeout: 5_000 },
    )
    .toBeGreaterThanOrEqual(4);
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitTranscript: (t: string) => void } }).__voiceTest.emitTranscript(
      "Speak at normal speed",
    );
  });
  await expect(paceBtn).toHaveAttribute("aria-pressed", "false");
  await expect(paceBtn).toHaveText("Slower pace");

  const typeToggleBtn = page.locator("#call-type-toggle-btn");
  await typeToggleBtn.click();
  await expect(page.locator("#call-text-form")).toBeVisible();
  await page.locator("#call-text-input").press("Escape");
  await expect(page.locator("#call-text-form")).toBeHidden();
  await expect(page.locator("#call-modal-backdrop")).toHaveClass(/open/);

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
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(3);
  await expect(page.locator("article.message-row-user .msg-spoken-tag").first()).toContainText("Spoken");
  await page.locator("#close-call-btn").click();
  await expect(page.locator("#open-call-btn")).toHaveAttribute("title", "Call receptionist");

  // Header 3-dot Kebab menu (#header-kebab-btn -> #header-options-menu) opens and Escape closes & returns focus.
  const kebabBtn = page.locator("#header-kebab-btn");
  await kebabBtn.click();
  await expect(kebabBtn).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#header-options-menu")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(kebabBtn).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#header-options-menu")).toBeHidden();
  await expect(kebabBtn).toBeFocused();

  // The header is part of the main canvas (no separate bar); the sidebar keeps its institutional blue with white text.
  const headerStyles = await page.locator(".chat-header").evaluate((el) => {
    const s = getComputedStyle(el);
    return { bg: s.backgroundColor, color: s.color };
  });
  expect(headerStyles).toEqual({ bg: "rgba(0, 0, 0, 0)", color: "rgb(11, 25, 44)" });
  const railStyles = await page.locator(".rail-wrap").evaluate((el) => {
    const s = getComputedStyle(el);
    return { bg: s.backgroundColor, color: s.color };
  });
  expect(railStyles).toEqual({ bg: "rgb(30, 64, 175)", color: "rgb(255, 255, 255)" });
  const mainBg = await page.locator(".app-content").evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(mainBg).toBe("rgba(0, 0, 0, 0)");
  const canvas = await page.locator(".ssra-main-gradient").evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(canvas).toContain("radial-gradient");

  const langselBtn = page.locator("#langsel-btn");
  await expect(langselBtn).toHaveAttribute("aria-expanded", "false");
  await langselBtn.click();
  await expect(langselBtn).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("dialog", { name: "Response language" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /^English/ })).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("ArrowUp");
  await expect(page.getByRole("radio", { name: /Auto-detect/ })).toBeFocused();
  await page.getByRole("radio", { name: /Auto-detect/ }).click();
  await expect(langselBtn).toHaveAttribute("aria-expanded", "false");
  await expect(langselBtn).toBeFocused();
  await expect(page.locator("#lang-auto-badge")).toBeVisible();

  // Main chat composer voice mode button couples with auto-narrate, replaces #ssra-chat-form with VoiceModeDock (page.tsx {voiceDock ?? <ChatInput />}), never opens Call Receptionist, and Escape exits.
  const voiceModeBtn = page.locator("#composer-voicemode-btn");
  await voiceModeBtn.click();
  await expect(page.locator("#voice-mode-dock")).toBeVisible();
  await expect(page.locator("#ssra-chat-form")).toBeHidden();
  await expect(page.locator("#call-modal-backdrop")).not.toHaveClass(/open/);
  await expect(page.locator("#voice-mode-dock")).toHaveAttribute("data-phase", "listening");
  await expect(page.locator("#voice-mode-dock")).toHaveAttribute("data-floor", "listening");
  await expect(page.locator("#voice-dock-primary")).toHaveAttribute("data-action", "send");
  await page.keyboard.press("Escape");
  await expect(page.locator("#voice-mode-dock")).toBeHidden();
  await expect(page.locator("#ssra-chat-form")).toBeVisible();
  await expect(voiceModeBtn).toHaveAttribute("aria-pressed", "false");

  // Single primary circle slot transition: empty composer shows Auto Voice (#composer-voicemode-btn); typing transitions to Send (#ssra-chat-submit).
  const dictateBtn = page.locator('.composer-tools-right [data-testid="composer-mic"]');
  await expect(dictateBtn).toBeVisible();
  await expect(dictateBtn).toHaveAttribute("data-tip", "Dictate");
  await expect(voiceModeBtn).toBeVisible();
  await expect(page.locator("#ssra-chat-submit")).toBeHidden();
  const composerBox = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composerBox.fill("Calculate PAYE on");
  await expect(voiceModeBtn).toBeHidden();
  await expect(page.locator("#ssra-chat-submit")).toBeVisible();
  await composerBox.fill("");
  await expect(voiceModeBtn).toBeVisible();
  await expect(page.locator("#ssra-chat-submit")).toBeHidden();
  await voiceModeBtn.click(); // enters voice mode (autoNarrate=true)
  await page.locator("#voice-dock-end").click(); // exits voice mode & sets autoNarrate=false
  await composerBox.fill("Calculate PAYE on");
  await dictateBtn.click();
  await expect(dictateBtn).toHaveClass(/btn-recording/);
  await expect(page.locator("#composer-rec-confirm")).toHaveAttribute("aria-label", "Stop and insert voice text");
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitTranscript: (t: string) => void } }).__voiceTest.emitTranscript(
      "250,000 SSP",
    );
  });
  await expect(composerBox).toHaveValue("Calculate PAYE on 250,000 SSP");
  await expect(page.locator("#composer-hint")).toContainText("Voice text added. Check it before you send.");
  await expect(page.locator("#ssra-chat-submit")).toBeVisible();
  await composerBox.fill("");

  // Interim speech preview & manual Confirm checkmark (#composer-rec-confirm) insertion
  await dictateBtn.click();
  await expect(page.locator("#composer-recording-bar")).toBeVisible();
  await page.evaluate(() => {
    (window as unknown as { __voiceTest: { emitInterimTranscript: (t: string) => void } }).__voiceTest.emitInterimTranscript(
      "What is the WHT rate on technical fees?",
    );
  });
  await expect(page.locator("#composer-rec-text")).toContainText("What is the WHT rate on technical fees?");
  await page.locator("#composer-rec-confirm").click();
  await expect(composerBox).toHaveValue("What is the WHT rate on technical fees?");
  await expect(page.locator("#composer-recording-bar")).toBeHidden();
  await expect(page.locator("#ssra-chat-submit")).toBeVisible();
  await composerBox.fill("");

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
  await expect(page.locator("#doc-modal-copilot-steps li")).toHaveCount(2);
  await page.locator("#doc-modal-report-btn").click();
  await expect(page.locator("#composer-hint")).toContainText("Inspection receipt downloaded");
  await page.locator("#doc-modal-prompts [data-doc-prompt]").first().click();
  await expect(page.locator("#doc-inspect-modal-backdrop")).not.toHaveClass(/open/);
  await expect(page.locator("article.message-row-assistant:not([aria-busy])")).toHaveCount(4);

  // Conversation report export from the 3-dot menu (pdf_export.py parity)
  await page.locator("#header-kebab-btn").click();
  await page.locator("#export-conv-report-btn").click();
  await expect(page.locator("#composer-hint")).toContainText("Conversation report downloaded.");

  await chip.locator("[data-remove-att]").click();
  await expect(chip).toHaveCount(0);
});

