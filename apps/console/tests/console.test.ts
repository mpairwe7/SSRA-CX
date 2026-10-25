import { describe, expect, it } from "vitest";
import { buildJitElevationBannerView, evaluateJitAdminElevation } from "../src/jit-admin.js";
import {
  authorizeConsoleAccess,
  authorizeConsoleRoute,
  executeConsoleProxy,
  KNOWLEDGE_RELEASE_STEPS,
} from "../src/proxy.js";
import {
  aiCallsHeadline,
  buildAgentQueueWorkbench,
  buildAnalyticsDashboardView,
  buildAuditorDriftAndFairnessView,
  buildAuditorEvidencePackage,
  buildAuditorTrailIntegrityView,
  buildCallBriefCardView,
  buildCallConsoleBarView,
  buildEvaluationDashboardView,
  buildForensicReplayTimelineView,
  buildKeycloakAuthorizationUrl,
  buildKeycloakOidcEndpoints,
  buildKillSwitchControlPlaneView,
  buildKnowledgeReleaseGovernanceView,
  buildKnowledgeReleasePipelineView,
  buildMakerCheckerCardView,
  buildOpsPageShell,
  buildOpsStatTile,
  buildSignInPageViewModel,
  buildSignUpPageViewModel,
  buildStaffDocumentInspectionViewerState,
  buildStaffReplyComposerPreview,
  buildSystemConnectorsHealthView,
  buildTakeoverHandbackBannerView,
  EVAL_METRIC_PLAIN_LABELS,
  evaluateAuditorQaRubricSubmission,
  evaluateAuthorityStatusResponse,
  formatSafeTimestamp,
  isLiveOfficer,
  looksLikeJwt,
  partitionCallDeskQueueSections,
  plainSeconds,
  pointsHint,
  previousWindow,
  QUANTILE_PLAIN_LABELS,
  RULE_BASED_BRIEF_ATTRIBUTION,
  resolveAgentQueueHotkey,
  resolveCallWorkspaceState,
  resolveExtractedFieldReview,
  resolveTelemetryProvenance,
  sanitizeAuthToken,
  sanitizeReturnTo,
  signedInName,
  splitMeasureParts,
  staffDestinationsFor,
  staffLandingPath,
  ticketRef,
  timingSafeEqualStrings,
  toDelta,
  validateAdminAnswerOverride,
  validateCopilotDraftApproval,
  validateOidcCallbackParams,
  validateOidcRedirectUri,
  validateWrapUpFormSubmission,
  waitingFor,
  waitTone,
  watchesLiveQueue,
} from "../src/views.js";

describe("@ssra/console ASVS L3 Passkey & Knowledge Release Workflow", () => {
  it("enforces WebAuthn passkey verification and 15-minute idle session timeout", () => {
    expect(KNOWLEDGE_RELEASE_STEPS).toHaveLength(6);
    expect(
      authorizeConsoleAccess({
        staffId: "stf_01",
        role: "legal_approver",
        passkeyVerified: false,
        officeCode: "JUBA_HQ",
        idleAgeSeconds: 60,
      }),
    ).toEqual({ allowed: false, reason: "WEBAUTHN_PASSKEY_REQUIRED" });

    expect(
      authorizeConsoleAccess({
        staffId: "stf_01",
        role: "legal_approver",
        passkeyVerified: true,
        officeCode: "JUBA_HQ",
        idleAgeSeconds: 120,
        originHeader: "null",
        allowedOrigin: "https://console.ssra.gov.ss",
      }),
    ).toEqual({ allowed: false, reason: "NULL_OR_UNTRUSTED_ORIGIN" });

    expect(
      authorizeConsoleAccess({
        staffId: "stf_01",
        role: "legal_approver",
        passkeyVerified: true,
        officeCode: "JUBA_HQ",
        idleAgeSeconds: 120,
        originHeader: "https://evil.example.com",
        allowedOrigin: "https://console.ssra.gov.ss",
      }),
    ).toEqual({ allowed: false, reason: "NULL_OR_UNTRUSTED_ORIGIN" });

    expect(
      authorizeConsoleAccess({
        staffId: "stf_01",
        role: "legal_approver",
        passkeyVerified: true,
        officeCode: "JUBA_HQ",
        idleAgeSeconds: 120,
        originHeader: "https://console.ssra.gov.ss",
        allowedOrigin: "https://console.ssra.gov.ss",
      }),
    ).toEqual({ allowed: true });

    const session = {
      staffId: "stf_01",
      role: "agent" as const,
      passkeyVerified: true,
      officeCode: "JUBA_HQ",
      idleAgeSeconds: 30,
      originHeader: "https://console.ssra.gov.ss",
      allowedOrigin: "https://console.ssra.gov.ss",
    };
    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_01",
        decision: "APPROVE_AND_SEND",
        citationsIncluded: [],
      }),
    ).toEqual({
      valid: false,
      error: "PRINCIPLE_1_GROUNDED_OR_SILENT_CITATIONS_REQUIRED",
    });

    expect(authorizeConsoleRoute(session, "/admin/kill-switches")).toEqual({
      allowed: false,
      reason: "INSUFFICIENT_ROLE_ADMIN_REQUIRED",
    });
    expect(authorizeConsoleRoute(session, "/knowledge-release/approve")).toEqual({
      allowed: false,
      reason: "INSUFFICIENT_ROLE_LEGAL_APPROVER_REQUIRED",
    });
    expect(
      authorizeConsoleRoute({ ...session, role: "admin" }, "/admin/kill-switches").allowed,
    ).toBe(true);
    expect(executeConsoleProxy({ session: null, pathname: "/admin/kill-switches" }).status).toBe(
      401,
    );
    expect(executeConsoleProxy({ session, pathname: "/admin/kill-switches" })).toEqual({
      status: 403,
      allowed: false,
      reason: "INSUFFICIENT_ROLE_ADMIN_REQUIRED",
    });
    expect(
      executeConsoleProxy({
        session: { ...session, role: "admin" },
        pathname: "/admin/kill-switches",
      }),
    ).toEqual({ status: 200, allowed: true });

    const pipeline = buildKnowledgeReleasePipelineView(3);
    expect(pipeline[3]?.state).toBe("ACTIVE");

    // Honest telemetry provenance, crash-safe timestamps, plain-language supervisor captions & trend deltas
    expect(formatSafeTimestamp(Number.NaN)).toBe("—");
    expect(formatSafeTimestamp(null)).toBe("—");
    expect(formatSafeTimestamp(1792152000)).not.toBe("—");
    expect(plainSeconds(850)).toBe("850 milliseconds");
    expect(plainSeconds(1400)).toBe("1.4 seconds");
    expect(QUANTILE_PLAIN_LABELS.p95).toBe("19 in 20 are faster");
    expect(EVAL_METRIC_PLAIN_LABELS.numeric_accuracy?.plainLabel).toBe(
      "Zero fabricated tax figures",
    );
    expect(splitMeasureParts("850 milliseconds")).toEqual({
      figure: "850",
      gap: " ",
      unit: "milliseconds",
    });
    expect(splitMeasureParts("1d 8h 55m")).toEqual({
      figure: "1d 8h 55m",
      gap: "",
      unit: null,
    });

    const prev = previousWindow(120, 220);
    expect(prev).toBe(100);
    const delta = toDelta(120, prev);
    const tile = buildOpsStatTile({
      label: QUANTILE_PLAIN_LABELS.p95,
      technicalSubtitle: "Chat p95 latency",
      formattedValue: plainSeconds(850),
      provenance: "LIVE_TELEMETRY",
      scope: "WINDOW_SCOPED",
      delta,
      higherIsBetter: false,
    });
    expect(tile.figure).toBe("850");
    expect(tile.unit).toBe(" milliseconds");
    expect(tile.deltaText).toBe("+20%");
    expect(tile.semanticDeltaClass).toBe("is-bad");

    const fallbackShell = buildOpsPageShell({
      eyebrow: "Observe",
      title: "Answer evaluation",
      description: "RAG quality evidence",
      provenance: "ILLUSTRATIVE_FALLBACK",
      allMetricsPassed: true,
    });
    expect(fallbackShell.mainId).toBe("staff-main");
    expect(fallbackShell.allGatesPassClaimAllowed).toBe(false);
    expect(fallbackShell.provenanceBanner).toContain("Illustrative sample");
    expect(resolveTelemetryProvenance({ observedAtMs: null, nowMs: 100_000 })).toBe(
      "UNKNOWN_TELEMETRY",
    );
    expect(resolveTelemetryProvenance({ observedAtMs: 10_000, nowMs: 400_001 })).toBe(
      "STALE_TELEMETRY",
    );
    expect(
      resolveTelemetryProvenance({
        observedAtMs: 99_000,
        nowMs: 100_000,
        isSyntheticBaseline: true,
      }),
    ).toBe("ILLUSTRATIVE_FALLBACK");

    // Analytics, Evaluation, Quality Audit & Agent Queue Dashboards
    const telemetryNow = 1_792_152_000_000;
    const analyticsView = buildAnalyticsDashboardView({
      p95TtftMs: 850,
      previousP95TtftMs: 1000,
      containmentRatePct: 96,
      citationPrecisionPct: 100,
      replicaUptimeHours: 72,
      telemetryObservedAtMs: telemetryNow - 30_000,
      nowMs: telemetryNow,
    });
    expect(analyticsView.liveGauges).toHaveLength(3);
    expect(analyticsView.ciVerifiedTargets).toHaveLength(3);
    expect(analyticsView.ciVerifiedTargets[0]?.provenance).toBe("CI_VERIFIED_TARGET");
    expect(analyticsView.replicaLifetimeTile.scope).toBe("REPLICA_LIFETIME");
    expect(analyticsView.shell.allGatesPassClaimAllowed).toBe(true);
    const unknownAnalyticsView = buildAnalyticsDashboardView({
      p95TtftMs: 850,
      containmentRatePct: 96,
      citationPrecisionPct: 100,
      replicaUptimeHours: 72,
      nowMs: telemetryNow,
    });
    expect(unknownAnalyticsView.liveGauges[0]?.provenance).toBe("UNKNOWN_TELEMETRY");
    expect(unknownAnalyticsView.shell.allGatesPassClaimAllowed).toBe(false);
    expect(unknownAnalyticsView.shell.provenanceBanner).toContain("freshness is unknown");
    const staleAnalyticsView = buildAnalyticsDashboardView({
      p95TtftMs: 850,
      containmentRatePct: 96,
      citationPrecisionPct: 100,
      replicaUptimeHours: 72,
      telemetryObservedAtMs: telemetryNow - 6 * 60_000,
      nowMs: telemetryNow,
    });
    expect(staleAnalyticsView.liveGauges[0]?.provenance).toBe("STALE_TELEMETRY");
    expect(staleAnalyticsView.shell.allGatesPassClaimAllowed).toBe(false);

    const evalView = buildEvaluationDashboardView({
      liveEvalMetrics: null,
      staticFallbackMetrics: [
        { name: "numeric_accuracy", value: 1.0, threshold: 1.0, passed: true },
      ],
    });
    expect(evalView.isLive).toBe(false);
    expect(evalView.shell.allGatesPassClaimAllowed).toBe(false);
    expect(evalView.rows[0]?.plainQuestion).toBe("Zero fabricated tax figures");
    const unTimestampedEvalView = buildEvaluationDashboardView({
      liveEvalMetrics: [{ name: "numeric_accuracy", value: 1, threshold: 1, passed: true }],
      staticFallbackMetrics: [],
      nowMs: telemetryNow,
    });
    expect(unTimestampedEvalView.isLive).toBe(false);
    expect(unTimestampedEvalView.provenance).toBe("UNKNOWN_TELEMETRY");

    expect(pointsHint(76, 72)).toBe("up 4 points from 72% in the period before");
    const callHeadline = aiCallsHeadline([
      { asked: 10, answered: 8, positive: 6, previousAnswered: 5, previousPositivePct: 60 },
      { asked: 5, answered: 2, positive: 2, previousAnswered: 5, previousPositivePct: 80 },
    ]);
    expect(callHeadline.positivePct).toBe(80);
    expect(callHeadline.previousPositivePct).toBe(70);

    expect(evaluateAuthorityStatusResponse(401, { fresh: false }).state).toBe("AUTH_OR_HTTP_ERROR");
    expect(evaluateAuthorityStatusResponse(200, { fresh: true, sources_checked: 16 })).toEqual({
      state: "FRESH",
      sourcesCheckedText: "16",
    });

    const nowSec = 1_792_152_000;
    expect(ticketRef("#tic-abcdef1234")).toBe("TIC-ABCDEF12");
    expect(waitingFor(nowSec - 7200, nowSec * 1000)).toBe("2h");
    expect(waitTone(nowSec - 90_000, null, null, nowSec * 1000, "open")).toBe("breach");
    expect(waitTone(nowSec - 90_000, null, null, nowSec * 1000, "resolved")).toBe("ok");

    const wb = buildAgentQueueWorkbench({
      tickets: [
        { id: "t_norm", status: "open", priority: "normal", created_at: nowSec - 300 },
        { id: "t_urg", status: "open", priority: "urgent", created_at: nowSec - 60 },
      ],
      view: { status: "open", mine: false, ticket: null },
      officerHandle: "officer_juba_1",
      nowMs: nowSec * 1000,
    });
    expect(wb.activeId).toBe("t_urg");
    expect(wb.claimCaseTransition("t_urg")).toEqual({
      status: "assigned",
      mine: true,
      ticket: "t_urg",
    });

    // 3 Role-Based Dashboards (ssra_staff, ssra_admin, ssra_auditor), Call Desk & WORM Audit Trail
    expect(staffLandingPath("ssra_staff")).toBe("/agent");
    expect(staffLandingPath("ssra_admin")).toBe("/admin");
    expect(staffLandingPath("ssra_auditor")).toBe("/analytics");
    expect(isLiveOfficer("ssra_staff")).toBe(true);
    expect(isLiveOfficer("ssra_admin")).toBe(false);
    expect(isLiveOfficer("ssra_auditor")).toBe(false);
    expect(watchesLiveQueue("ssra_staff")).toBe(true);
    expect(watchesLiveQueue("ssra_auditor")).toBe(true);
    expect(watchesLiveQueue("ssra_admin")).toBe(false);
    expect(
      signedInName({ external_id: "keycloak|6a7d7af3ace1faccc70dc644", role: "ssra_staff" }),
    ).toBe("Tax agent · …c70dc644".replace("c7", ""));
    expect(staffDestinationsFor("ssra_staff").map((d) => d.href)).toContain("/agent");
    expect(staffDestinationsFor("ssra_admin").map((d) => d.href)).toContain("/admin");
    expect(staffDestinationsFor("ssra_auditor").map((d) => d.href)).toContain("/admin/audit");

    // Officer Call Desk: only ssra_staff can take a waiting call; auditors watch read-only
    const staffCallDesk = resolveCallWorkspaceState({
      role: "ssra_staff",
      callStatus: "transferring",
      claimedByOfficer: null,
      isMyActiveCall: false,
      isWrapUpPending: false,
    });
    expect(staffCallDesk.state).toBe("waiting");
    expect(staffCallDesk.canTakeCall).toBe(true);

    const auditorCallDesk = resolveCallWorkspaceState({
      role: "ssra_auditor",
      callStatus: "transferring",
      claimedByOfficer: null,
      isMyActiveCall: false,
      isWrapUpPending: false,
    });
    expect(auditorCallDesk.canTakeCall).toBe(false);

    // Auditor WORM Audit Trail & Merkle Seal Inspector
    const intactAudit = buildAuditorTrailIntegrityView(
      {
        valid: true,
        head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
        unsealed_rows: 4,
        breaks: [],
        anchor_breaks: [],
      },
      { role: "ssra_admin" },
    );
    expect(intactAudit.chipText).toBe("Record intact");
    expect(intactAudit.sealButtonDisabled).toBe(false);

    // Separation of Duties: ssra_staff and ssra_auditor cannot seal WORM batches
    const staffAuditView = buildAuditorTrailIntegrityView(
      {
        valid: true,
        head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
        unsealed_rows: 4,
        breaks: [],
        anchor_breaks: [],
      },
      { role: "ssra_staff" },
    );
    expect(staffAuditView.sealButtonDisabled).toBe(true);

    const alteredAudit = buildAuditorTrailIntegrityView({
      valid: false,
      head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
      unsealed_rows: 4,
      breaks: [{ seq: 12, reason: "hash mismatch" }],
      anchor_breaks: [],
    });
    expect(alteredAudit.chipText).toBe("Record altered");
    expect(alteredAudit.compromisedFromSeq).toBe(12);
    expect(alteredAudit.sealButtonDisabled).toBe(true);
    expect(alteredAudit.explanation).toContain("Event #12 fails its check");

    // Auditor Read-Only Separation of Duties at Console Request Boundary
    const auditorSession = { ...session, role: "ssra_auditor" as const };
    expect(
      executeConsoleProxy({
        session: auditorSession,
        pathname: "/admin/flags",
        method: "POST",
      }),
    ).toEqual({
      status: 403,
      allowed: false,
      reason: "AUDITOR_READ_ONLY_SEPARATION_OF_DUTIES",
    });
    expect(
      executeConsoleProxy({
        session: auditorSession,
        pathname: "/v1/conversations/conv_1/qa-score",
        method: "POST",
      }),
    ).toEqual({ status: 200, allowed: true });
    expect(staffDestinationsFor("ssra_auditor").map((d) => d.href)).toContain("/admin/replay");

    // Forensic Conversation Replay Timeline, Sampled QA Rubric, Drift/Fairness & Evidence Exporter
    const replayTimeline = buildForensicReplayTimelineView({
      threadId: "thr_forensic_1",
      turns: [
        {
          turn_index: 1,
          thread_id: "thr_forensic_1",
          channel: "web",
          locale: "en",
          auth_level: "T1_TIN_BOUND",
          subject_ref: "sub_taxpayer_amina_01",
          redacted_input: "Check my balance for TIN ••••1234",
          intent_name: "get_balance",
          risk_tier: "T1",
          policy_decision: "ALLOW",
          prompt_version: "2026.10.1",
          model_route: "ssra-sovereign/sunflower-qwen3.5-9b",
          knowledge_snapshot_version: "2026.10.1",
          tool_calls: [{ id: "art_1", server: "ledger", tool: "get_balance" }],
          citations: ["Ledger-••••1234"],
          numbers: [{ value: "1450000", unit: "SSP", source_ref: "art_1.total_outstanding_ssp" }],
          output_text: "Your balance is 1,450,000 SSP.",
          abstained: false,
          safety_flags: [],
          audit_event_hash: "a".repeat(64),
        },
      ],
    });
    expect(replayTimeline.allTurnsReconstructable).toBe(true);
    expect(replayTimeline.flaggedTurnsCount).toBe(0);
    expect(replayTimeline.turns[0]?.redactedInput).toBe("Check my balance for TIN ••••1234");

    const qaBelowGate = evaluateAuditorQaRubricSubmission({
      conversationId: "conv_1",
      auditorId: "aud_01",
      accuracy: 0.8,
      citationsComplete: 1.0,
      neutrality: 1.0,
      languageQuality: 1.0,
    });
    expect(qaBelowGate.valid).toBe(false);
    expect(qaBelowGate.requiresDiscrepancyTicket).toBe(true);

    const qaWithNote = evaluateAuditorQaRubricSubmission({
      conversationId: "conv_1",
      auditorId: "aud_01",
      accuracy: 0.8,
      citationsComplete: 1.0,
      neutrality: 1.0,
      languageQuality: 1.0,
      findingNote: "Missing citation anchor on BPT bracket",
    });
    expect(qaWithNote.valid).toBe(true);
    expect(qaWithNote.requiresDiscrepancyTicket).toBe(true);

    const driftAlert = buildAuditorDriftAndFairnessView({
      intentMixKlDivergence: 0.04,
      abstentionRate24h: 0.08,
      guardrailTriggerRate24h: 0.01,
      accuracyByLocale: { en: 1.0, pga: 0.91, ar: 0.99 },
    });
    expect(driftAlert.status).toBe("DRIFT_OR_PARITY_ALERT");
    expect(driftAlert.breachedLocales).toContain("pga");

    const blockedEvidence = buildAuditorEvidencePackage({
      auditReport: {
        valid: false,
        head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
        unsealed_rows: 1,
        breaks: [{ seq: 5, reason: "tampered digest" }],
        anchor_breaks: [],
      },
      snapshotVersion: "2026.10.1",
      sampledThreadIds: ["thr_1"],
      qaCompositeScore: 0.99,
    });
    expect(blockedEvidence.exportAllowed).toBe(false);

    const validEvidence = buildAuditorEvidencePackage({
      auditReport: {
        valid: true,
        head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
        unsealed_rows: 0,
        breaks: [],
        anchor_breaks: [],
      },
      snapshotVersion: "2026.10.1",
      sampledThreadIds: ["thr_1"],
      qaCompositeScore: 0.99,
    });
    expect(validEvidence.exportAllowed).toBe(true);

    // Staff Dashboard UI/UX: Queue filtering, hotkeys, priority SLA, Copilot safety, Takeover/Handback, Maker-Checker & RTL Composer
    const resolvedWb = buildAgentQueueWorkbench({
      tickets: [
        { id: "t_open", status: "open", priority: "urgent", created_at: nowSec - 8000 },
        { id: "t_done", status: "resolved", priority: "normal", created_at: nowSec - 9000 },
      ],
      view: { status: "resolved", mine: false, ticket: null },
      officerHandle: "officer_juba_1",
      nowMs: nowSec * 1000,
    });
    expect(resolvedWb.rows.map((r) => r.id)).toEqual(["t_done"]);
    expect(waitTone(nowSec - 7500, null, null, nowSec * 1000, "open", "urgent")).toBe("breach");

    expect(
      resolveAgentQueueHotkey({
        key: "j",
        rows: wb.rows,
        activeId: "t_urg",
        isTypingInInput: false,
      }),
    ).toEqual({
      handled: true,
      action: "select_ticket",
      targetTicketId: "t_norm",
    });
    expect(
      resolveAgentQueueHotkey({
        key: "a",
        rows: wb.rows,
        activeId: "t_urg",
        isTypingInInput: true,
      }).handled,
    ).toBe(false);

    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_01",
        decision: "EDIT_AND_SEND",
        citationsIncluded: ["Sec-1"],
        replyText: "Do not worry, your penalty is waived today.",
      }),
    ).toEqual({
      valid: false,
      error: "PROHIBITED_PROMISE_OR_CASH_SOLICITATION_BLOCKED",
    });
    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_01",
        decision: "EDIT_AND_SEND",
        citationsIncluded: ["Sec-1"],
        replyText: "Your TIN 1002001234 is active.",
      }),
    ).toEqual({
      valid: false,
      error: "UNMASKED_TIN_IN_OUTBOUND_REPLY_BLOCKED",
    });

    const takeoverBanner = buildTakeoverHandbackBannerView({
      role: "ssra_staff",
      currentStaffId: "stf_01",
      status: "STAFF_TAKEOVER",
      assignedStaffId: "stf_01",
      channel: "whatsapp",
      hoursSinceLastTaxpayerMessage: 30,
    });
    expect(takeoverBanner.canHandback).toBe(true);
    expect(takeoverBanner.requiresTemplateForOutbound).toBe(true);

    const mcSelf = buildMakerCheckerCardView({
      caseId: "case_01",
      actionType: "TCC_OVERRIDE",
      makerStaffId: "stf_01",
      currentStaffId: "stf_01",
      role: "ssra_staff",
      rationale: "Verified bank receipt",
    });
    expect(mcSelf.canApprove).toBe(false);

    const mcOk = buildMakerCheckerCardView({
      caseId: "case_01",
      actionType: "TCC_OVERRIDE",
      makerStaffId: "stf_01",
      currentStaffId: "stf_02",
      role: "ssra_staff",
      rationale: "Verified bank receipt",
    });
    expect(mcOk.canApprove).toBe(true);

    const resolvedField = resolveExtractedFieldReview(
      {
        id: "f2",
        name: "Total Payable",
        value: "SSP 150,000",
        confidence: 0.62,
        source: "ocr_inset",
        status: "review_required",
        page: 2,
      },
      "override_value",
      "SSP 180,000",
    );
    expect(resolvedField.status).toBe("auto_use");
    expect(resolvedField.value).toBe("SSP 180,000");

    const arPreview = buildStaffReplyComposerPreview({
      draftText: "يرجى الدفع عبر البوابة الرسمية https://etax.nra.gov.ss/",
      locale: "ar",
    });
    expect(arPreview.dir).toBe("rtl");
    expect(arPreview.hasOfficialPortalLink).toBe(true);
    expect(arPreview.estimatedSmsSegments).toBe(1);

    // Staff Document Inspection Viewer, Officer Call Brief Card & Wrap-Up Form
    const viewer = buildStaffDocumentInspectionViewerState({
      documentName: "assessment_scan.pdf",
      pageCount: 3,
      currentPage: 2,
      zoomLevel: 125,
      fields: [
        {
          id: "f1",
          name: "TIN",
          value: "••••1234",
          confidence: 0.98,
          source: "vector_glyph",
          status: "auto_use",
          page: 2,
        },
        {
          id: "f2",
          name: "Total Payable",
          value: "SSP 150,000",
          confidence: 0.62,
          source: "ocr_inset",
          status: "review_required",
          page: 2,
        },
      ],
    });
    expect(viewer.pageBadge).toBe("Page 2 of 3");
    expect(viewer.canvasScaleTransform).toBe("scale(1.25)");
    expect(viewer.reviewRequiredCount).toBe(1);
    expect(viewer.canCompleteDocumentReview).toBe(false);

    // Admin Dashboard UI/UX: JIT countdown, 5-Step Degradation Ladder, Knowledge Release Governance, Connectors & Overrides
    expect(
      evaluateJitAdminElevation({
        requesterStaffId: "stf_01",
        approverStaffId: "stf_02",
        passkeyVerified: true,
        devicePosture: {
          deviceId: "dev_1",
          diskEncrypted: true,
          edrActive: true,
          osPatchCurrent: true,
        },
        durationMinutes: 30,
        reason: "no",
      }),
    ).toEqual({ granted: false, reason: "JIT_REASON_TOO_SHORT" });

    const jitBanner = buildJitElevationBannerView({
      grantedAtMs: 1_000_000,
      durationMinutes: 30,
      nowMs: 1_000_000 + 28 * 60_000,
    });
    expect(jitBanner.state).toBe("EXPIRING_SOON");
    expect(jitBanner.mutationsUnlocked).toBe(true);

    const jitExpired = buildJitElevationBannerView({
      grantedAtMs: 1_000_000,
      durationMinutes: 30,
      nowMs: 1_000_000 + 35 * 60_000,
    });
    expect(jitExpired.state).toBe("EXPIRED");
    expect(jitExpired.mutationsUnlocked).toBe(false);

    const ksLocked = buildKillSwitchControlPlaneView({
      role: "ssra_admin",
      jitActive: false,
      degradationLevel: 4,
      disabledTools: ["ledger.get_balance"],
      disabledChannels: ["voice"],
    });
    expect(ksLocked.canApplyMutation).toBe(false);
    expect(ksLocked.llmGenerationActive).toBe(false);
    expect(ksLocked.deterministicCalculatorsActive).toBe(true);

    const krSelfApprove = buildKnowledgeReleaseGovernanceView({
      version: "2026.11.0",
      status: "LEGAL_REVIEW",
      draftAuthorId: "stf_admin_1",
      currentStaffId: "stf_admin_1",
      role: "ssra_admin",
      evalRegressionPassed: true,
    });
    expect(krSelfApprove.canApproveLegal).toBe(false);

    const krRollback = buildKnowledgeReleaseGovernanceView({
      version: "2026.11.0",
      status: "APPROVED",
      draftAuthorId: "stf_author_1",
      currentStaffId: "stf_admin_2",
      role: "ssra_admin",
      evalRegressionPassed: false,
    });
    expect(krRollback.autoRollbackTriggered).toBe(true);
    expect(krRollback.status).toBe("ROLLED_BACK");

    const connHealth = buildSystemConnectorsHealthView({
      etaxCircuit: "CLOSED",
      ecustomsCircuit: "CLOSED",
      bossCircuit: "CLOSED",
    });
    expect(connHealth.allHealthy).toBe(true);
    expect(connHealth.connectors).toHaveLength(3);

    expect(
      validateAdminAnswerOverride({
        role: "ssra_admin",
        questionPattern: "How do I pay tax?",
        overrideAnswerText: "Pay via https://etax.nra.gov.ss/ into designated banks.",
        sectionAnchor: "",
      }),
    ).toEqual({
      valid: false,
      error: "PRINCIPLE_1_SECTION_ANCHOR_CITATION_REQUIRED",
    });
    expect(
      validateAdminAnswerOverride({
        role: "ssra_admin",
        questionPattern: "How do I pay tax?",
        overrideAnswerText: "Pay via https://etax.nra.gov.ss/ into designated banks.",
        sectionAnchor: "Sec-1-Cash-Free-Collection",
      }).valid,
    ).toBe(true);

    const briefCard = buildCallBriefCardView({
      brief: {
        caller_goal: { text: "Unblock TIN ••••1234", turn_seqs: [1] },
        ai_already_said: [],
        still_open: [],
        details_given: [],
        sentiment: "frustrated",
        suggested_opener: "Hello, let's resolve your TIN issue.",
        turns_covered: 2,
        model: "ssra-sovereign/sunflower-qwen3.5-9b",
      },
      loading: false,
    });
    expect(briefCard.mode).toBe("full");
    expect(briefCard.moodLabel).toBe("Frustrated");
    const ruleBasedCard = buildCallBriefCardView({
      brief: {
        caller_goal: { text: "Unblock TIN ••••1234", turn_seqs: [1] },
        ai_already_said: [],
        still_open: [],
        details_given: [],
        sentiment: "calm",
        suggested_opener: "Hello, I'm an SSRA officer.",
        turns_covered: 1,
        model: null,
      },
      loading: false,
    });
    expect(ruleBasedCard.modelAttribution).toBe(RULE_BASED_BRIEF_ATTRIBUTION);

    expect(
      validateWrapUpFormSubmission({
        note: "",
        outcome: "resolved",
        satisfaction: 5,
        notSaid: false,
      }).valid,
    ).toBe(false);
    expect(
      validateWrapUpFormSubmission({
        note: "Caller TIN question resolved",
        outcome: "resolved",
        satisfaction: null,
        notSaid: true,
      }).valid,
    ).toBe(true);

    // 4-Section Call Desk Queue & CallConsoleBar
    const lobbySample = [
      {
        call_id: "c_wait_norm",
        status: "transferring" as const,
        priority: "normal" as const,
        started_at: 100,
        waiting_since: 110,
        claimed_by: "",
      },
      {
        call_id: "c_wait_urg",
        status: "transferring" as const,
        priority: "urgent" as const,
        started_at: 120,
        waiting_since: 125,
        claimed_by: "",
      },
      {
        call_id: "c_ai_risk",
        status: "ai" as const,
        priority: "normal" as const,
        started_at: 90,
        waiting_since: null,
        claimed_by: "",
        risk_level: "at_risk" as const,
      },
    ];
    const sections = partitionCallDeskQueueSections(lobbySample, null);
    expect(sections.waiting[0]?.call_id).toBe("c_wait_urg");
    expect(sections.ai[0]?.call_id).toBe("c_ai_risk");

    const barView = buildCallConsoleBarView({
      role: "ssra_staff",
      calls: lobbySample,
      myCallId: null,
      availability: "available",
      micReady: false,
      soundEnabled: true,
    });
    expect(barView.waitingCount).toBe(2);
    expect(barView.longestWaitingCallId).toBe("c_wait_norm");
    expect(barView.micButtonLabel).toBe("Check mic");
    expect(barView.micAttentionClass).toBe(true);

    // JIT Admin requires device posture + maker-checker approval
    expect(
      evaluateJitAdminElevation({
        requesterStaffId: "stf_01",
        approverStaffId: "stf_01", // self-approval forbidden
        passkeyVerified: true,
        devicePosture: {
          deviceId: "dev_1",
          diskEncrypted: true,
          edrActive: true,
          osPatchCurrent: true,
        },
        durationMinutes: 30,
        reason: "Emergency snapshot rollback",
      }),
    ).toEqual({ granted: false, reason: "MAKER_CHECKER_APPROVAL_REQUIRED" });

    expect(
      evaluateJitAdminElevation({
        requesterStaffId: "stf_01",
        approverStaffId: "stf_supervisor_02",
        passkeyVerified: true,
        devicePosture: {
          deviceId: "dev_1",
          diskEncrypted: true,
          edrActive: true,
          osPatchCurrent: true,
        },
        durationMinutes: 30,
        reason: "Emergency snapshot rollback",
      }),
    ).toEqual({ granted: true });

    // October 2026 QA/Security Audit Hardening: BFLA, NaN idle timeout, subject-binding, Arabic-Indic TINs, BiDi OCR & Evidence bounds
    expect(
      authorizeConsoleAccess({
        ...session,
        idleAgeSeconds: Number.NaN,
      }),
    ).toEqual({ allowed: false, reason: "SESSION_IDLE_EXPIRED" });
    expect(
      authorizeConsoleAccess({
        ...session,
        staffId: "   ",
      }),
    ).toEqual({ allowed: false, reason: "INVALID_STAFF_IDENTITY_CLAIMS" });
    expect(
      authorizeConsoleRoute({ ...session, role: "ssra_staff" }, "/admin/audit", "GET"),
    ).toEqual({
      allowed: false,
      reason: "INSUFFICIENT_ROLE_GOVERNANCE_OR_AUDIT_REQUIRED",
    });
    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_impersonated_other",
        decision: "APPROVE_AND_SEND",
        citationsIncluded: ["Sec-1"],
      }),
    ).toEqual({ valid: false, error: "STAFF_SUBJECT_MISMATCH_IN_ACTION" });
    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_01",
        decision: "EDIT_AND_SEND",
        citationsIncluded: ["Sec-1"],
      }),
    ).toEqual({ valid: false, error: "EMPTY_MANUAL_OR_EDITED_REPLY" });
    expect(
      validateCopilotDraftApproval(session, {
        conversationId: "conv_1",
        staffId: "stf_01",
        decision: "EDIT_AND_SEND",
        citationsIncluded: ["Sec-1"],
        replyText: "TIN ١٠٠-٢٠٠-١٢٣٤ is active.",
      }),
    ).toEqual({ valid: false, error: "UNMASKED_TIN_IN_OUTBOUND_REPLY_BLOCKED" });
    expect(
      validateAdminAnswerOverride({
        role: "ssra_admin",
        questionPattern: "TIN lookup",
        overrideAnswerText: "Use TIN 100-200-1234 as example.",
        sectionAnchor: "Sec-1",
      }),
    ).toEqual({ valid: false, error: "UNMASKED_TIN_IN_ANSWER_OVERRIDE_BLOCKED" });
    expect(
      buildAuditorTrailIntegrityView({
        valid: true,
        head_hash: "invalid_short_hash",
        unsealed_rows: 0,
        breaks: [],
        anchor_breaks: [],
      }).chipText,
    ).toBe("Record altered");
    expect(
      buildAuditorEvidencePackage({
        auditReport: {
          valid: true,
          head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
          unsealed_rows: 0,
          breaks: [],
          anchor_breaks: [],
        },
        snapshotVersion: "   ",
        sampledThreadIds: ["thr_1"],
        qaCompositeScore: 0.99,
      }).exportAllowed,
    ).toBe(false);
    const bidiField = resolveExtractedFieldReview(
      {
        id: "f_bidi",
        name: "Payee",
        value: "SSRA",
        confidence: 0.5,
        source: "ocr_inset",
        status: "review_required",
        page: 1,
      },
      "override_value",
      "\u202ESSRA Treasury\u202C",
    );
    expect(bidiField.value).toBe("SSRA Treasury");

    // Keycloak 26.4.11 OIDC + PKCE S256 + WebAuthn Passkey Sign-In, Sign-Up & Callback
    expect(executeConsoleProxy({ session: null, pathname: "/signin" }).status).toBe(200);
    expect(executeConsoleProxy({ session: null, pathname: "/signup" }).status).toBe(200);
    expect(executeConsoleProxy({ session: null, pathname: "/signin/callback" }).status).toBe(200);

    expect(sanitizeAuthToken(" \u200Bheader_b64.payload_b64.sig_b64…\n")).toBe(
      "header_b64.payload_b64.sig_b64",
    );
    expect(looksLikeJwt("hdr.pld.sig")).toBe(true);
    expect(looksLikeJwt("hdr.pld")).toBe(false);

    expect(sanitizeReturnTo("/admin/audit")).toBe("/admin/audit");
    expect(sanitizeReturnTo("//evil.example.com")).toBeUndefined();
    expect(sanitizeReturnTo("/\t/evil.example.com")).toBeUndefined();
    expect(sanitizeReturnTo("/\\evil.example.com")).toBeUndefined();
    expect(sanitizeReturnTo("javascript:alert(1)")).toBeUndefined();
    expect(sanitizeReturnTo("/signin")).toBeUndefined();
    expect(sanitizeReturnTo("/signin/callback")).toBeUndefined();
    expect(sanitizeReturnTo("/signup")).toBeUndefined();
    expect(sanitizeReturnTo("/api/flags")).toBeUndefined();
    expect(sanitizeReturnTo("/v1/admin/kill-switches")).toBeUndefined();

    const kcEndpoints = buildKeycloakOidcEndpoints("https://sso.ssra.gov.ss/realms/ssra/");
    expect(kcEndpoints.authorizationEndpoint).toBe(
      "https://sso.ssra.gov.ss/realms/ssra/protocol/openid-connect/auth",
    );
    expect(kcEndpoints.registrationEndpoint).toBe(
      "https://sso.ssra.gov.ss/realms/ssra/protocol/openid-connect/registrations",
    );
    expect(() => buildKeycloakOidcEndpoints("http://sso.ssra.gov.ss/realms/ssra")).toThrow();

    const signInAuth = buildKeycloakAuthorizationUrl({
      redirectUri: "https://console.ssra.gov.ss/signin/callback",
      codeChallenge: "c".repeat(43),
      state: "s".repeat(32),
      mode: "signin",
      prompt: "login",
      returnTo: "/analytics",
    });
    expect(signInAuth.url).toContain("client_id=ssra-staff-console");
    expect(signInAuth.url).toContain("code_challenge_method=S256");
    expect(signInAuth.url).toContain("acr_values=urn%3Assra%3Aacr%3Apasskey");
    expect(signInAuth.url).toContain("prompt=login");
    expect(signInAuth.sanitizedReturnTo).toBe("/analytics");

    const signUpAuth = buildKeycloakAuthorizationUrl({
      redirectUri: "https://console.ssra.gov.ss/signin/callback",
      codeChallenge: "c".repeat(43),
      state: "s".repeat(32),
      mode: "signup",
      returnTo: "//evil.com",
    });
    expect(signUpAuth.url).toContain("prompt=create");
    expect(signUpAuth.url).toContain("screen_hint=signup");
    expect(signUpAuth.sanitizedReturnTo).toBeUndefined();

    expect(
      validateOidcCallbackParams({
        code: "auth_code_1",
        state: "state_a",
        expectedState: "state_b",
        pkceVerifier: "v".repeat(64),
      }).errorReason,
    ).toBe("CSRF_STATE_MISMATCH");

    const cbAuditor = validateOidcCallbackParams({
      code: "auth_code_1",
      state: "s".repeat(32),
      expectedState: "s".repeat(32),
      pkceVerifier: "v".repeat(64),
      iss: "https://sso.ssra.gov.ss/realms/ssra",
      resolvedRole: "ssra_auditor",
    });
    expect(cbAuditor.valid).toBe(true);
    expect(cbAuditor.targetPath).toBe("/analytics");
    expect(cbAuditor.allowedDestinations.map((d) => d.href)).toContain("/admin/audit");

    const signInVm = buildSignInPageViewModel({ selectedRole: "ssra_staff" });
    expect(signInVm.targetLandingPath).toBe("/agent");
    const signUpVm = buildSignUpPageViewModel();
    expect(signUpVm.benefits).toHaveLength(3);
    expect(validateOidcRedirectUri("https://console.ssra.gov.ss/signin/callback")).toBe(
      "https://console.ssra.gov.ss/signin/callback",
    );
    expect(() => validateOidcRedirectUri("http://evil.example.com/signin/callback")).toThrow();
    expect(() => validateOidcRedirectUri("https://console.ssra.gov.ss/other")).toThrow();
    expect(timingSafeEqualStrings("abc123", "abc123")).toBe(true);
    expect(timingSafeEqualStrings("abc123", "abc124")).toBe(false);
    expect(timingSafeEqualStrings("short", "longer_string")).toBe(false);

    // RFC 9207 OAuth Mix-Up Attack detection on callback iss parameter (mandatory & exact match)
    expect(
      validateOidcCallbackParams({
        code: "auth_code_1",
        state: "s".repeat(32),
        expectedState: "s".repeat(32),
        pkceVerifier: "v".repeat(64),
        iss: "https://evil-idp.example.com/realms/ssra",
      }).errorReason,
    ).toBe("RFC9207_ISSUER_MISMATCH");

    expect(
      validateOidcCallbackParams({
        code: "auth_code_1",
        state: "s".repeat(32),
        expectedState: "s".repeat(32),
        pkceVerifier: "v".repeat(64),
      }).errorReason,
    ).toBe("RFC9207_ISSUER_MISMATCH");

    expect(
      validateOidcCallbackParams({
        code: "auth_code_1",
        state: "s".repeat(32),
        expectedState: "s".repeat(32),
        pkceVerifier: "v".repeat(64),
        iss: "https://sso.ssra.gov.ss/realms/ssra/",
      }).errorReason,
    ).toBe("RFC9207_ISSUER_MISMATCH");

    expect(
      validateOidcCallbackParams({
        code: "auth_code_1",
        state: "s".repeat(32),
        expectedState: "s".repeat(32),
        pkceVerifier: "v".repeat(64),
        iss: "https://sso.ssra.gov.ss/realms/ssra",
      }).valid,
    ).toBe(true);
    expect(
      validateOidcCallbackParams({
        code: "bad code with spaces",
        state: "s".repeat(32),
        expectedState: "s".repeat(32),
        pkceVerifier: "v".repeat(64),
      }).errorReason,
    ).toBe("INVALID_AUTH_CODE");
  });
});
