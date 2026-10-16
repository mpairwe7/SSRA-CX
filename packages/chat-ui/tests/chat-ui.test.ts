import { describe, expect, it } from "vitest";
import {
  escapeHtmlStrict,
  GENERATIVE_UI_STORYBOOK_FIXTURES,
  OfflineOutboxQueue,
  parseAguiSseStream,
  renderGenerativeUICard,
  resolveGenerativeUIComponent,
  validateMcpAppIframe,
  validateVoiceNoteSubmission,
  verifyAllStorybookFixturesRenderAccessibly,
} from "../src/index.js";

describe("@ssra/chat-ui Generative UI Registry", () => {
  it("accepts registered components with valid Zod 4 props", () => {
    const resolved = resolveGenerativeUIComponent(
      {
        name: "CalculatorForm",
        props: {
          calculator_type: "PAYE",
          gross_monthly_ssp: "250000",
          estimated_tax_ssp: "25000",
          net_monthly_ssp: "225000",
          effective_rate_percent: "10",
          filing_deadline_day: 15,
          is_estimate: true,
        },
      },
      "Fallback PAYE estimate text",
    );
    expect(resolved.mode).toBe("component");
    expect(resolved.componentName).toBe("CalculatorForm");
  });

  it("falls back safely to plain text for unknown components, invalid props, or 2G low-data mode", () => {
    const unknown = resolveGenerativeUIComponent(
      { name: "RawHtmlScriptInjector", props: { html: "<script>alert(1)</script>" } },
      "Safe plain text",
    );
    expect(unknown.mode).toBe("text_fallback");
    expect(unknown.componentName).toBeNull();

    // Unmasked TIN in BalanceCard is rejected by Zod regex /^••••\d{4}$/
    const unmasked = resolveGenerativeUIComponent(
      {
        name: "BalanceCard",
        props: {
          tin_masked: "1002001234",
          total_outstanding_ssp: "0",
          currency: "SSP",
          filing_status: "COMPLIANT",
          as_of: "2026-10-16",
        },
      },
      "Safe plain text",
    );
    expect(unmasked.mode).toBe("text_fallback");

    // 2G Low-data mode forces plain text
    const lowData = resolveGenerativeUIComponent(
      {
        name: "HandoffCard",
        props: { reason: "USER_REQUEST" },
      },
      "Safe plain text",
      { lowDataMode: true },
    );
    expect(lowData.mode).toBe("text_fallback");
  });

  it("parses resumable AG-UI SSE streams and enforces T0-only offline outbox policy", () => {
    const sampleSse = [
      'id: evt_1\nevent: agui\ndata: {"type":"RUN_STARTED","threadId":"thr_1"}',
      'id: evt_2\nevent: agui\ndata: {"type":"TEXT_MESSAGE_CONTENT","delta":"PAYE is due by day 15."}',
      'id: evt_3\nevent: agui\ndata: {"type":"RUN_FINISHED","threadId":"thr_1"}',
      "",
    ].join("\n\n");

    const parsed = parseAguiSseStream(sampleSse, { afterEventId: "evt_1" });
    expect(parsed.events).toHaveLength(2);
    expect(parsed.lastEventId).toBe("evt_3");
    expect(parsed.accumulatedText).toBe("PAYE is due by day 15.");

    const outbox = new OfflineOutboxQueue(2);
    expect(
      outbox.enqueue({
        id: "q_pii",
        message: "My TIN is 1002001234",
        locale: "en",
        tier: "T0",
        queuedAtIso: "2026-10-16T08:00:00Z",
      }),
    ).toEqual({
      queued: false,
      reason: "SECURITY_POLICY_PII_REJECTED_FROM_OFFLINE_QUEUE",
    });
    expect(
      outbox.enqueue({
        id: "q_1",
        message: "How do I get a TIN?",
        locale: "en",
        tier: "T0",
        queuedAtIso: "2026-10-16T08:00:00Z",
      }).queued,
    ).toBe(true);

    // T1 personal queries must never be written to shared-device offline storage
    expect(
      outbox.enqueue({
        id: "q_2",
        message: "Check my tax balance",
        locale: "en",
        tier: "T1",
        queuedAtIso: "2026-10-16T08:01:00Z",
      }),
    ).toEqual({
      queued: false,
      reason: "SECURITY_POLICY_T0_ONLY_OFFLINE_QUEUE",
    });

    const card = renderGenerativeUICard(
      {
        name: "BalanceCard",
        props: {
          tin_masked: "••••5678",
          total_outstanding_ssp: "1450000",
          currency: "SSP",
          filing_status: "FILING_DUE",
          as_of: "2026-10-16",
        },
      },
      "Fallback",
      { locale: "ar" },
    );
    expect(card.mode).toBe("component");
    expect(card.dir).toBe("rtl");
    expect(card.safeHtml).toContain('data-component="BalanceCard"');
    expect(escapeHtmlStrict("<script>")).toBe("&lt;script&gt;");

    const okApp = validateMcpAppIframe("https://apps.ssra.gov.ss/widgets/calculator");
    expect(okApp.allowed).toBe(true);
    expect(okApp.sandboxAttr).toBe("allow-scripts");

    const badApp = validateMcpAppIframe("https://untrusted.example.com/widget");
    expect(badApp.allowed).toBe(false);
    expect(badApp.reason).toBe("UNALLOWLISTED_MCP_APP_ORIGIN");

    // Phase 4 Voice notes require recording consent and low-bitrate Opus codec
    expect(
      validateVoiceNoteSubmission({
        locale: "pga",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 18,
        sizeBytes: 38_000,
        recordingConsentGranted: false,
      }),
    ).toEqual({ accepted: false, reason: "VOICE_RECORDING_CONSENT_REQUIRED" });

    expect(
      validateVoiceNoteSubmission({
        locale: "pga",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 18,
        sizeBytes: 38_000,
        recordingConsentGranted: true,
      }),
    ).toEqual({ accepted: true });

    expect(GENERATIVE_UI_STORYBOOK_FIXTURES).toHaveLength(7);
    expect(verifyAllStorybookFixturesRenderAccessibly()).toBe(true);
  });
});
