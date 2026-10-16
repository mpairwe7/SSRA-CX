import { describe, expect, it } from "vitest";
import { evaluateJitAdminElevation } from "../src/jit-admin.js";
import { authorizeConsoleAccess, KNOWLEDGE_RELEASE_STEPS } from "../src/proxy.js";
import {
  aiCallsHeadline,
  buildAgentQueueWorkbench,
  buildAnalyticsDashboardView,
  buildAuditorTrailIntegrityView,
  buildEvaluationDashboardView,
  buildKnowledgeReleasePipelineView,
  buildOpsPageShell,
  buildOpsStatTile,
  EVAL_METRIC_PLAIN_LABELS,
  evaluateAuthorityStatusResponse,
  formatSafeTimestamp,
  isLiveOfficer,
  plainSeconds,
  pointsHint,
  previousWindow,
  QUANTILE_PLAIN_LABELS,
  resolveCallWorkspaceState,
  signedInName,
  splitMeasureParts,
  staffDestinationsFor,
  staffLandingPath,
  ticketRef,
  toDelta,
  validateCopilotDraftApproval,
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
    expect(fallbackShell.provenanceBanner).toContain("Illustrative fallback");

    // Analytics, Evaluation, Quality Audit & Agent Queue Dashboards
    const analyticsView = buildAnalyticsDashboardView({
      p95TtftMs: 850,
      previousP95TtftMs: 1000,
      containmentRatePct: 96,
      citationPrecisionPct: 100,
      replicaUptimeHours: 72,
    });
    expect(analyticsView.liveGauges).toHaveLength(3);
    expect(analyticsView.ciVerifiedTargets).toHaveLength(3);
    expect(analyticsView.ciVerifiedTargets[0]?.provenance).toBe("CI_VERIFIED_TARGET");
    expect(analyticsView.replicaLifetimeTile.scope).toBe("REPLICA_LIFETIME");

    const evalView = buildEvaluationDashboardView({
      liveEvalMetrics: null,
      staticFallbackMetrics: [
        { name: "numeric_accuracy", value: 1.0, threshold: 1.0, passed: true },
      ],
    });
    expect(evalView.isLive).toBe(false);
    expect(evalView.shell.allGatesPassClaimAllowed).toBe(false);
    expect(evalView.rows[0]?.plainQuestion).toBe("Zero fabricated tax figures");

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
    const intactAudit = buildAuditorTrailIntegrityView({
      valid: true,
      head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
      unsealed_rows: 4,
      breaks: [],
      anchor_breaks: [],
    });
    expect(intactAudit.chipText).toBe("Record intact");
    expect(intactAudit.sealButtonDisabled).toBe(false);

    const alteredAudit = buildAuditorTrailIntegrityView({
      valid: false,
      head_hash: "8f2b1290a5b1179c20f9e8123ab71e8902112a01",
      unsealed_rows: 4,
      breaks: [{ seq: 12, reason: "hash mismatch" }],
      anchor_breaks: [],
    });
    expect(alteredAudit.chipText).toBe("Record altered");
    expect(alteredAudit.sealButtonDisabled).toBe(true);
    expect(alteredAudit.explanation).toContain("Event #12 fails its check");

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
  });
});
