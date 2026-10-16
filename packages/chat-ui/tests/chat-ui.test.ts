import { describe, expect, it } from "vitest";
import {
  buildCallReceptionistScreen,
  buildChatComposerState,
  buildDocumentInspectionModalView,
  buildFloatingChatHeader,
  cleanMarkdownForSpeech,
  computeCallOrbFrame,
  createRevealQueue,
  escapeHtmlStrict,
  evaluateCaptionScrollPin,
  formatDocType,
  GENERATIVE_UI_STORYBOOK_FIXTURES,
  groupConversationsByRecency,
  isCspSafeImagePreviewDataUrl,
  joinDictated,
  nextRevealIndex,
  OfflineOutboxQueue,
  parseAguiSseStream,
  renderGenerativeUICard,
  resolveGenerativeUIComponent,
  stripStepPrefix,
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
    expect(() => new OfflineOutboxQueue(0)).toThrow(RangeError);
    expect(
      outbox.enqueue({
        id: "q_pii",
        message: "My TIN is 100 200 1234",
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
    expect(
      outbox.enqueue({
        id: "q_1b",
        message: "What is the BPT rate?",
        locale: "en",
        tier: "T0",
        queuedAtIso: "2026-10-16T08:01:00Z",
      }).queued,
    ).toBe(true);
    expect(
      outbox.enqueue({
        id: "q_over_cap",
        message: "Third T0 message exceeds capacity",
        locale: "en",
        tier: "T0",
        queuedAtIso: "2026-10-16T08:02:00Z",
      }),
    ).toEqual({
      queued: false,
      reason: "OFFLINE_OUTBOX_CAPACITY_EXCEEDED",
    });

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

    // Chatv2 word-boundary reveal queue, floating header, single-toggle voice mode, and rail grouping
    expect(nextRevealIndex("PAYE is due on the 15th", 0, 5)).toBe(8); // snaps to "PAYE is "
    const committed: string[] = [];
    const rq = createRevealQueue({
      onCommit: (txt) => committed.push(txt),
      instant: true,
    });
    rq.push("PAYE is 0% up to 300,000 SSP.");
    expect(committed.at(-1)).toBe("PAYE is 0% up to 300,000 SSP.");

    const floatingHdr = buildFloatingChatHeader({
      hasStartedChat: true,
      railCollapsed: true,
      railPeekHover: true,
      conversationTitle: "PAYE Filing 2026",
      conversationPinned: true,
      locale: "en",
    });
    expect(floatingHdr.railPeekActive).toBe(true);
    expect(floatingHdr.restoreFocusToTriggerBeforeModal).toBe(true);

    expect(joinDictated("How do I", "register for TIN?")).toBe("How do I register for TIN?");
    const compState = buildChatComposerState({
      message: "",
      isLoading: false,
      isRecording: true,
      voiceMode: true,
      audioLevels: [0.1, 0.5, 0.8, 0.4, 0.2],
      dictationNotice: "Listening in Juba Arabic…",
    });
    expect(compState.narrationEnabled).toBe(true);
    expect(compState.primaryAction).toBe("mic");
    expect(compState.waveformBars).toHaveLength(5);

    expect(
      cleanMarkdownForSpeech("Visit **https://etax.nra.gov.ss/** [Sec-18] for `TIN` registration."),
    ).toBe("Visit official SSRA portal for TIN registration.");

    const nowMs = 1_792_152_000_000;
    const grouped = groupConversationsByRecency(
      [
        { id: "c1", title: "Pinned TIN Guide", updatedAtMs: nowMs - 500_000_000, pinned: true },
        { id: "c2", title: "Today PAYE", updatedAtMs: nowMs - 1_000 },
        { id: "c3", title: "Yesterday Customs", updatedAtMs: nowMs - 100_000_000 },
      ],
      nowMs,
    );
    expect(grouped.pinned).toHaveLength(1);
    expect(grouped.today).toHaveLength(1);
    expect(grouped.yesterday).toHaveLength(1);

    // Call Receptionist (Pre-call consent, CallLanguageChip, CallOrb echo tie-breaker, scroll pin)
    const preCall = buildCallReceptionistScreen({
      status: "consent",
      durationSeconds: 0,
      language: "pga",
      languageName: "Juba Arabic",
      languageSource: "auto",
    });
    expect(preCall.viewMode).toBe("pre_call_consent");
    expect(preCall.languageChip.chipLabel).toBe("Juba Arabic · auto");

    const liveCall = buildCallReceptionistScreen({
      status: "ai",
      durationSeconds: 75,
      language: "pga",
      languageName: "Juba Arabic",
      languageSource: "override",
    });
    expect(liveCall.viewMode).toBe("live_call");
    expect(liveCall.formattedDuration).toBe("01:15");
    expect(liveCall.languageChip.chipLabel).toBe("Juba Arabic · chosen");
    expect(liveCall.canRequestOfficer).toBe(true);

    // Playback wins ties over mic input so speaker echo never flickers the orb to listening
    const orbSpeaking = computeCallOrbFrame({
      active: true,
      prefersReducedMotion: false,
      previousSmoothed: 0,
      inputLevel: 0.4,
      outputLevel: 0.4,
    });
    expect(orbSpeaking.mode).toBe("speaking");
    expect(orbSpeaking.smoothedLevel).toBeGreaterThan(0);

    const orbReduced = computeCallOrbFrame({
      active: true,
      prefersReducedMotion: true,
      previousSmoothed: 0.5,
      inputLevel: 0.8,
      outputLevel: 0.8,
    });
    expect(orbReduced.mode).toBe("idle");
    expect(orbReduced.smoothedLevel).toBe(0);

    expect(
      evaluateCaptionScrollPin({ scrollHeight: 1000, scrollTop: 680, clientHeight: 300 })
        .pinnedToBottom,
    ).toBe(true);
    expect(
      evaluateCaptionScrollPin({ scrollHeight: 1000, scrollTop: 500, clientHeight: 300 })
        .showJumpToLatest,
    ).toBe(true);

    // Document & Screenshot Inspection Modal
    expect(stripStepPrefix("Step 1: Click Refresh")).toBe("Click Refresh");
    expect(formatDocType("portal_screenshot", "pga")).toBe("Sura ta Mawqi SSRA e-Tax");
    const modalView = buildDocumentInspectionModalView(
      {
        id: "doc_1",
        name: "etax_500.png",
        sizeBytes: 204_800,
        docType: "portal_screenshot",
        analysis: {
          documentId: "doc_1",
          filename: "etax_500.png",
          kind: "image",
          sizeBytes: 204_800,
          docType: "portal_screenshot",
          confidence: 0.95,
          fields: { tins: ["••••1234"] },
          taxReconciliation: { status: "discrepancy_detected", variance_ssp: 12000 },
          screenshot_guidance: {
            is_screenshot: true,
            detected_portal: "SSRA National e-Tax Portal",
            portal_url: "https://etax.nra.gov.ss/",
            steps: ["Step 1: Wait 60 seconds and refresh"],
          },
        },
      },
      "en",
    );
    expect(modalView.isScreenshot).toBe(true);
    expect(modalView.normalizedSteps).toEqual(["Wait 60 seconds and refresh"]);
    expect(modalView.quickPrompts.length).toBeGreaterThanOrEqual(3);
    expect(isCspSafeImagePreviewDataUrl("data:image/jpeg;base64,/9j/4AAQSkZJRg==")).toBe(true);
    expect(isCspSafeImagePreviewDataUrl("blob:https://assist.ssra.gov.ss/123")).toBe(false);
  });
});
