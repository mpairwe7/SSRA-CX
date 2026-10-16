import { describe, expect, it } from "vitest";
import { evaluateJitAdminElevation } from "../src/jit-admin.js";
import { authorizeConsoleAccess, KNOWLEDGE_RELEASE_STEPS } from "../src/proxy.js";
import {
  buildKnowledgeReleasePipelineView,
  buildOpsPageShell,
  buildOpsStatTile,
  EVAL_METRIC_PLAIN_LABELS,
  formatSafeTimestamp,
  plainSeconds,
  previousWindow,
  QUANTILE_PLAIN_LABELS,
  splitMeasureParts,
  toDelta,
  validateCopilotDraftApproval,
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
