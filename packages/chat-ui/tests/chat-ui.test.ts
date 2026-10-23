import { describe, expect, it } from "vitest";
import {
  AUDIO_SIGNIFIER_SPECS,
  buildCallReceptionistScreen,
  buildChatComposerState,
  buildDocumentInspectionModalView,
  buildFloatingChatHeader,
  buildHumanSubtleMicrocopy,
  buildNarrationBarView,
  calculateOfflinePayeEstimate,
  calculateOfflineWithholdingEstimate,
  cleanMarkdownForSpeech,
  computeCallOrbFrame,
  createRevealQueue,
  EndOfTurnDetector,
  escapeHtmlStrict,
  evaluateCaptionScrollPin,
  evaluateSemanticEndpointing,
  evaluateVoiceTurnContinuation,
  formatDocType,
  GENERATIVE_UI_STORYBOOK_FIXTURES,
  groupConversationsByRecency,
  isBackchannelText,
  isCspSafeImagePreviewDataUrl,
  isLikelyAssistantEcho,
  isVocalAcousticProfile,
  joinDictated,
  levelDbfs,
  MAX_CONSECUTIVE_SPEECH_RETRIES,
  nextRevealIndex,
  OFFLINE_SSRA_OFFICE_DIRECTORY,
  OfflineOutboxQueue,
  POST_TTS_ECHO_COOLDOWN_MS,
  parseAguiSseStream,
  renderGenerativeUICard,
  resolveAdaptiveVoiceNetworkProfile,
  resolveGenerativeUIComponent,
  stripStepPrefix,
  validateMcpAppIframe,
  validateVoiceNoteSubmission,
  verifyAllStorybookFixturesRenderAccessibly,
  verifyOfflineOfficialChannel,
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
    expect(parsed.corrupted).toBe(false);

    // Corrupt frame stops advancing lastEventId before the gap
    const corruptSse = [
      'id: evt_1\nevent: agui\ndata: {"type":"RUN_STARTED","threadId":"thr_1"}',
      "id: evt_corrupt\nevent: agui\ndata: {truncated-json-on-2g",
      'id: evt_3\nevent: agui\ndata: {"type":"RUN_FINISHED","threadId":"thr_1"}',
    ].join("\n\n");
    const parsedCorrupt = parseAguiSseStream(corruptSse);
    expect(parsedCorrupt.corrupted).toBe(true);
    expect(parsedCorrupt.lastEventId).toBe("evt_1");

    const whtCard = renderGenerativeUICard(
      {
        name: "CalculatorForm",
        props: {
          category: "rent",
          gross_amount_ssp: "500000",
          rate_percent: "10",
          withholding_tax_ssp: "50000",
          net_payable_ssp: "450000",
          is_estimate: true,
        },
      },
      "WHT estimate",
    );
    expect(whtCard.mode).toBe("component");
    expect(whtCard.safeHtml).toContain("WHT: 50000 SSP");

    // Reject contradictory PAYE + WHT tax props
    const mixedCalc = renderGenerativeUICard(
      {
        name: "CalculatorForm",
        props: {
          estimated_tax_ssp: "100",
          withholding_tax_ssp: "20",
          is_estimate: true,
        },
      },
      "Fallback",
    );
    expect(mixedCalc.mode).toBe("text_fallback");

    const timelineCard = renderGenerativeUICard(
      {
        name: "FilingStatusTimeline",
        props: {
          tin_masked: "••••1234",
          filing_status: "COMPLIANT",
          last_filed_period: "2026-09",
          as_of: "2026-10-20",
        },
      },
      "Filing timeline",
    );
    expect(timelineCard.mode).toBe("component");
    expect(timelineCard.safeHtml).toContain("Period 2026-09, as of 2026-10-20");

    // Rich CitationList with guided_steps & HandoffCard human-reassuring header + subtle microcopy
    const guidedCitationCard = renderGenerativeUICard(
      {
        name: "CitationList",
        props: {
          citations: [
            {
              id: "cit_tin_1",
              snapshot_version: "2026.10.1",
              doc_title: "SSRA e-Tax Portal Guide",
              section_anchor: "Part-I-Sec-1-TIN-Registration",
              effective_from: "2021-07-01",
              url: "https://etax.nra.gov.ss/",
            },
          ],
          guided_steps: [
            {
              step_number: 1,
              title: "Select Applicant Category",
              instruction: "Apply online at https://etax.nra.gov.ss/",
            },
          ],
        },
      },
      "Register for TIN on e-Tax.",
    );
    expect(guidedCitationCard.mode).toBe("component");
    expect(guidedCitationCard.safeHtml).toContain("ssra-guided-steps");
    expect(guidedCitationCard.safeHtml).toContain("Step 1: Select Applicant Category");
    expect(guidedCitationCard.safeHtml).toContain("ssra-citation-badges");

    const handoffCard = renderGenerativeUICard(
      {
        name: "HandoffCard",
        props: {
          reason: "T4_POLICY",
          queue: "DOMESTIC_TAX",
          priority: "HIGH",
        },
      },
      "Routing to SSRA Officer.",
    );
    expect(handoffCard.mode).toBe("component");
    expect(handoffCard.safeHtml).toContain("SSRA Officer Assistance (DOMESTIC_TAX)");
    expect(escapeHtmlStrict("`backtick` & 'quote'")).toContain("&#96;backtick&#96;");

    const microAr = buildHumanSubtleMicrocopy("searching", "ar", false);
    expect(microAr.dir).toBe("rtl");
    expect(microAr.showPulseIndicator).toBe(true);
    const mobileHdr = buildFloatingChatHeader({
      hasStartedChat: true,
      railCollapsed: false,
      railPeekHover: true,
      viewportWidthPx: 360,
      locale: "en",
    });
    expect(mobileHdr.compactMobileMode).toBe(true);
    expect(mobileHdr.railPeekActive).toBe(false);

    const outbox = new OfflineOutboxQueue(2);
    expect(() => new OfflineOutboxQueue(0)).toThrow(RangeError);
    expect(
      outbox.enqueue({
        id: "q_natid",
        message: "My National ID is R12345678",
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
        id: "q_natid_ar",
        message: "My National ID is R١٢٣٤٥٦٧٨",
        locale: "ar",
        tier: "T0",
        queuedAtIso: "2026-10-16T08:00:00Z",
      }),
    ).toEqual({
      queued: false,
      reason: "SECURITY_POLICY_PII_REJECTED_FROM_OFFLINE_QUEUE",
    });
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
    expect(grouped.dateUnavailable).toHaveLength(0);
    const corruptDated = groupConversationsByRecency(
      [
        { id: "invalid", title: "Unreadable date", updatedAtMs: Number.NaN },
        { id: "future", title: "Future date", updatedAtMs: nowMs + 8 * 86_400_000 },
      ],
      nowMs,
    );
    expect(corruptDated.dateUnavailable.map((item) => item.id)).toEqual(["future", "invalid"]);

    // Call Receptionist (Pre-call consent, CallLanguageChip, CallOrb echo tie-breaker, scroll pin)
    const preCall = buildCallReceptionistScreen({
      status: "consent",
      durationSeconds: 0,
      language: "pga",
      languageName: "Juba Arabic",
      languageSource: "auto",
      recording: false,
    });
    expect(preCall.viewMode).toBe("pre_call_consent");
    expect(preCall.languageChip.chipLabel).toBe("Juba Arabic · auto");
    expect(preCall.statusPillTone).toBe("not_started");
    expect(preCall.speakingWith).toBe("none");

    const liveCall = buildCallReceptionistScreen({
      status: "ai",
      durationSeconds: 75,
      language: "pga",
      languageName: "Juba Arabic",
      languageSource: "override",
      recording: true,
    });
    expect(liveCall.viewMode).toBe("live_call");
    expect(liveCall.formattedDuration).toBe("01:15");
    expect(liveCall.languageChip.chipLabel).toBe("Juba Arabic · chosen");
    expect(liveCall.canRequestOfficer).toBe(true);
    expect(liveCall.speakingWith).toBe("automated_assistant");
    expect(liveCall.recordingIndicator).toBe(true);
    const officerCall = buildCallReceptionistScreen({
      status: "on_hold",
      durationSeconds: 200,
      language: "en",
      languageName: "English",
      languageSource: "auto",
      recording: false,
    });
    expect(officerCall.speakingWith).toBe("officer");
    expect(officerCall.recordingIndicator).toBe(false);

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
    // Reduced motion stops the animation but still reports who has the floor.
    expect(orbReduced.mode).toBe("speaking");
    expect(orbReduced.smoothedLevel).toBe(0);

    // Multi-turn voice continuation, 450ms post-TTS echo guard, backchannel immunity & retry bound
    expect(POST_TTS_ECHO_COOLDOWN_MS).toBe(450);
    expect(MAX_CONSECUTIVE_SPEECH_RETRIES).toBe(3);
    expect(isBackchannelText("uh-huh")).toBe(true);
    expect(isBackchannelText("نعم")).toBe(true);
    expect(isBackchannelText("What is PAYE?")).toBe(false);
    expect(
      isLikelyAssistantEcho({
        transcript: "file the return via the e-Tax portal",
        lastAssistantText: "Please file the return via the e-Tax portal by the 15th.",
        elapsedSinceTtsEndMs: 200,
      }),
    ).toBe(true);
    expect(
      evaluateVoiceTurnContinuation({
        transcript: "file the return via the e-Tax portal",
        lastAssistantText: "Please file the return via the e-Tax portal by the 15th.",
        assistantSpeaking: false,
        elapsedSinceTtsEndMs: 200,
        consecutiveEmptyRetries: 0,
        continuousEnabled: true,
      }).action,
    ).toBe("ignore_echo");
    expect(
      evaluateVoiceTurnContinuation({
        transcript: "mm-hm",
        lastAssistantText: "Please file the return via the e-Tax portal by the 15th.",
        assistantSpeaking: true,
        elapsedSinceTtsEndMs: 0,
        consecutiveEmptyRetries: 0,
        continuousEnabled: true,
      }).action,
    ).toBe("ignore_backchannel");
    expect(
      evaluateVoiceTurnContinuation({
        transcript: "How do I apply for a Tax Compliance Certificate?",
        lastAssistantText: "Please file the return via the e-Tax portal by the 15th.",
        assistantSpeaking: false,
        elapsedSinceTtsEndMs: 600,
        consecutiveEmptyRetries: 2,
        continuousEnabled: true,
      }),
    ).toEqual({
      action: "submit_turn",
      nextRetryCount: 0,
      resumeDelayMs: 450,
    });
    expect(
      evaluateVoiceTurnContinuation({
        transcript: "",
        lastAssistantText: "",
        assistantSpeaking: false,
        elapsedSinceTtsEndMs: 900,
        consecutiveEmptyRetries: 3,
        continuousEnabled: true,
      }).action,
    ).toBe("pause_after_retries");

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
      },
      "en",
    );
    expect(modalView.analysisStatus).toBe("unavailable");
    expect(modalView.isScreenshot).toBe(false);
    expect(modalView.portalUrl).toBeNull();
    expect(modalView.normalizedSteps).toEqual([]);
    expect(modalView.quickPrompts).toEqual([]);
    expect(isCspSafeImagePreviewDataUrl("data:image/jpeg;base64,/9j/4AAQSkZJRg==")).toBe(true);
    expect(isCspSafeImagePreviewDataUrl("blob:https://assist.ssra.gov.ss/123")).toBe(false);

    // EndOfTurnDetector, Vocal Acoustic Profile, Earcons & WCAG 2.2 SC 1.4.2 NarrationBar
    const silentSamples = new Float32Array(256);
    silentSamples[0] = Number.NaN;
    expect(levelDbfs(silentSamples)).toBe(-100);
    expect(isVocalAcousticProfile(silentSamples)).toBe(true);
    const eot = new EndOfTurnDetector({ silenceMs: 800, minSpeechMs: 200, noSpeechMs: 4000 });
    expect(eot.push(Number.NaN, Number.NaN)).toBeNull();
    expect(eot.push(-65, 0)).toBeNull();
    expect(eot.push(-65, 350)).toBeNull(); // room floor calibrated
    expect(eot.push(-25, 450)).toBeNull(); // burst starts
    expect(eot.push(-25, 650)).toBe("speech"); // 200ms speech reached
    expect(eot.hasSpeech).toBe(true);
    expect(eot.push(-70, 1500)).toBe("end"); // >800ms silence after speech

    expect(AUDIO_SIGNIFIER_SPECS.micStart.startHz).toBe(440);
    expect(AUDIO_SIGNIFIER_SPECS.micStart.endHz).toBe(880);

    const narBar = buildNarrationBarView({
      active: true,
      loading: false,
      paused: false,
      failed: false,
      sentence: "PAYE is due by the 15th of the following month.",
    });
    expect(narBar.mode).toBe("playing");
    expect(narBar.stopKeyShortcut).toBe("Escape");
    expect(narBar.sentenceAriaHidden).toBe(true);

    const narFailed = buildNarrationBarView({
      active: false,
      loading: false,
      paused: false,
      failed: true,
      sentence: null,
    });
    expect(narFailed.mode).toBe("failed");
    expect(narFailed.showRetry).toBe(true);

    // Semantic Endpointing & Offline Statutory Resilience Pack (October 2026 Voice & 2G Flows)
    expect(evaluateSemanticEndpointing("My TIN is 1002").effectiveSilenceMs).toBe(1100);
    expect(evaluateSemanticEndpointing("رقمي ١٠٠٢").effectiveSilenceMs).toBe(1100);
    expect(evaluateSemanticEndpointing("Check my balance ku").effectiveSilenceMs).toBe(1100);
    expect(evaluateSemanticEndpointing("What is the PAYE rate?").effectiveSilenceMs).toBe(420);

    const offlinePaye = calculateOfflinePayeEstimate(250_000);
    // Matches seed-2026.10.1.yaml: 0..50k @ 0% (0) + 50k..150k @ 10% (10,000) + 150k..250k @ 15% (15,000) = 25,000 SSP
    expect(offlinePaye.estimatedTaxSsp).toBe(25_000);
    expect(offlinePaye.netMonthlySsp).toBe(225_000);
    expect(offlinePaye.isOfflinePack).toBe(true);
    const offlineWht = calculateOfflineWithholdingEstimate(500_000, "rent");
    // Matches seed-2026.10.1.yaml: wht.rent.rate_percent = 10% -> 50,000 SSP
    expect(offlineWht.ratePercent).toBe(10);
    expect(offlineWht.withholdingTaxSsp).toBe(50_000);
    expect(offlineWht.netPayableSsp).toBe(450_000);
    expect(OFFLINE_SSRA_OFFICE_DIRECTORY).toHaveLength(4);
    expect(verifyOfflineOfficialChannel("https://etax.nra.gov.ss/").status).toBe(
      "OFFICIAL_VERIFIED",
    );
    expect(verifyOfflineOfficialChannel("https://etax.nra.gov.ss/login").status).toBe(
      "OFFICIAL_VERIFIED",
    );
    expect(verifyOfflineOfficialChannel("etax.nra.gov.ss").status).toBe("OFFICIAL_VERIFIED");
    expect(verifyOfflineOfficialChannel("cash-collector-phone").status).toBe("UNVERIFIED_OR_SCAM");
    expect(resolveAdaptiveVoiceNetworkProfile({ effectiveType: "2g" }).opusBitrateKbps).toBe(12);
    expect(resolveAdaptiveVoiceNetworkProfile({ effectiveType: "4g" }).opusBitrateKbps).toBe(24);

    // VR-AR1: Offline T0 Opus Voice-Note Outbox Queue (<= 64 KB, <= 30s, consent-gated)
    const vnOutbox = new OfflineOutboxQueue(1);
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_t1_rejected",
        locale: "pga",
        tier: "T1",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 15,
        sizeBytes: 24_000,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("SECURITY_POLICY_T0_ONLY_OFFLINE_QUEUE");
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_no_consent",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 15,
        sizeBytes: 24_000,
        recordingConsentGranted: false,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("VOICE_RECORDING_CONSENT_REQUIRED");
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_nan_dur",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: Number.NaN,
        sizeBytes: 24_000,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("EXCEEDS_30S_OFFLINE_VOICE_NOTE_CAP");
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_zero_dur",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 0,
        sizeBytes: 24_000,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("EXCEEDS_30S_OFFLINE_VOICE_NOTE_CAP");
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_nan_size",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 30,
        sizeBytes: Number.NaN,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("EXCEEDS_64KB_OFFLINE_VOICE_NOTE_CAP");
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_t0_ok",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 30,
        sizeBytes: 65_536,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).queued,
    ).toBe(true);
    expect(
      vnOutbox.enqueueVoiceNote({
        id: "vn_cap_exceeded",
        locale: "pga",
        tier: "T0",
        mimeType: "audio/webm;codecs=opus",
        durationSeconds: 10,
        sizeBytes: 12_000,
        recordingConsentGranted: true,
        queuedAtIso: "2026-10-20T10:00:00Z",
      }).reason,
    ).toBe("OFFLINE_OUTBOX_CAPACITY_EXCEEDED");
    expect(vnOutbox.drainVoiceNotes()).toHaveLength(1);
  });
});
