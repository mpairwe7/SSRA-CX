/**
 * Auditor Forensic Replay Inspector, Sampled QA Rubric Workbench, Online Drift/Fairness Monitor,
 * and ISO/IEC 42001 / EU AI Act Art. 12 Cryptographic Evidence Exporter
 * (`apps/console/src/auditor-workbench.ts` — Principle 9, Sections 12.3, 14.2, Gate 2 & Gate 3).
 */

import { type AuditVerificationReport, buildAuditorTrailIntegrityView } from "./roles-and-audit.js";
import { buildOpsPageShell, type OpsPageShellDescriptor } from "./views.js";

const HEX64_PATTERN = /^[0-9a-f]{64}$/i;

export interface ReconstructedTurnItem {
  readonly turn_index: number;
  readonly thread_id: string;
  readonly channel: string;
  readonly locale: string;
  readonly auth_level: string;
  readonly subject_ref: string | null;
  readonly redacted_input: string;
  readonly intent_name: string;
  readonly risk_tier: "T0" | "T1" | "T2" | "T3" | "T4";
  readonly policy_decision: "ALLOW" | "DENY" | "STEP_UP" | "HANDOFF";
  readonly prompt_version: string;
  readonly model_route: string;
  readonly knowledge_snapshot_version: string;
  readonly tool_calls: readonly {
    readonly id: string;
    readonly server: string;
    readonly tool: string;
  }[];
  readonly citations: readonly string[];
  readonly numbers: readonly {
    readonly value: string;
    readonly unit: string;
    readonly source_ref: string;
  }[];
  readonly output_text: string;
  readonly abstained: boolean;
  readonly safety_flags: readonly string[];
  readonly audit_event_hash: string;
}

export interface ForensicReplayTurnView {
  readonly turnIndex: number;
  readonly redactedInput: string;
  readonly riskTier: string;
  readonly policyDecision: string;
  readonly shortAuditHash: string;
  readonly hasSafetyTrigger: boolean;
  readonly isUncitedNonAbstained: boolean;
  readonly hasUnattributedNumber: boolean;
  readonly requiresAuditorAttention: boolean;
  readonly plainSummary: string;
}

export interface ForensicReplayTimelineView {
  readonly shell: OpsPageShellDescriptor;
  readonly threadId: string;
  readonly totalTurns: number;
  readonly flaggedTurnsCount: number;
  readonly allTurnsReconstructable: boolean;
  readonly turns: readonly ForensicReplayTurnView[];
}

/**
 * Build the Principle 9 Turn-by-Turn Forensic Conversation Replay timeline view for `ssra_auditor`.
 */
export function buildForensicReplayTimelineView(params: {
  readonly threadId: string;
  readonly turns: readonly ReconstructedTurnItem[];
}): ForensicReplayTimelineView {
  const turnViews: ForensicReplayTurnView[] = params.turns.map((t) => {
    const shortAuditHash = HEX64_PATTERN.test(t.audit_event_hash)
      ? `${t.audit_event_hash.slice(0, 10)}…`
      : "unverified";
    const hasSafetyTrigger = t.safety_flags.length > 0;
    const isUncitedNonAbstained = !t.abstained && t.citations.length === 0;
    const hasUnattributedNumber = t.numbers.some(
      (n) => !n.source_ref || n.source_ref.trim().length === 0,
    );
    const requiresAuditorAttention =
      hasSafetyTrigger ||
      isUncitedNonAbstained ||
      hasUnattributedNumber ||
      t.policy_decision === "DENY";

    return {
      turnIndex: t.turn_index,
      redactedInput: t.redacted_input,
      riskTier: t.risk_tier,
      policyDecision: t.policy_decision,
      shortAuditHash,
      hasSafetyTrigger,
      isUncitedNonAbstained,
      hasUnattributedNumber,
      requiresAuditorAttention,
      plainSummary: `Tier ${t.risk_tier} ${t.policy_decision} · ${t.tool_calls.length} tool call(s) · ${t.citations.length} citation(s) · ${t.numbers.length} verified figure(s)`,
    };
  });

  const allTurnsReconstructable =
    params.turns.length > 0 &&
    params.turns.every(
      (t) =>
        HEX64_PATTERN.test(t.audit_event_hash) &&
        Boolean(t.prompt_version) &&
        Boolean(t.model_route) &&
        Boolean(t.knowledge_snapshot_version),
    );
  const flaggedTurnsCount = turnViews.filter((t) => t.requiresAuditorAttention).length;

  const shell = buildOpsPageShell({
    eyebrow: "Audit",
    title: "Forensic conversation replay",
    description:
      "Turn-by-turn reconstruction of redacted inputs, OPA policy decisions, tool artifacts, citations, and WORM hashes",
    provenance: params.turns.length > 0 ? "LIVE_TELEMETRY" : "ILLUSTRATIVE_FALLBACK",
    allMetricsPassed: allTurnsReconstructable && flaggedTurnsCount === 0,
  });

  return {
    shell,
    threadId: params.threadId,
    totalTurns: turnViews.length,
    flaggedTurnsCount,
    allTurnsReconstructable,
    turns: turnViews,
  };
}

export interface AuditorQaRubricInput {
  readonly conversationId: string;
  readonly auditorId: string;
  readonly accuracy: number;
  readonly citationsComplete: number;
  readonly neutrality: number;
  readonly languageQuality: number;
  readonly findingNote?: string | undefined;
}

export interface AuditorQaRubricOutcome {
  readonly valid: boolean;
  readonly error: string | null;
  readonly compositeScore: number | null;
  readonly requiresDiscrepancyTicket: boolean;
}

/**
 * Validate an auditor's sampled QA rubric score (`POST /v1/conversations/{id}/qa-score`)
 * and require a discrepancy finding note whenever any dimension falls below launch gates.
 */
export function evaluateAuditorQaRubricSubmission(
  input: AuditorQaRubricInput,
): AuditorQaRubricOutcome {
  const scores = [input.accuracy, input.citationsComplete, input.neutrality, input.languageQuality];
  if (scores.some((s) => !Number.isFinite(s) || s < 0 || s > 1)) {
    return {
      valid: false,
      error: "All QA rubric scores must be finite numbers between 0.0 and 1.0",
      compositeScore: null,
      requiresDiscrepancyTicket: false,
    };
  }
  const compositeScore =
    Math.round(
      ((input.accuracy + input.citationsComplete + input.neutrality + input.languageQuality) / 4) *
        10000,
    ) / 10000;
  const belowGate =
    input.accuracy < 1.0 ||
    input.citationsComplete < 0.95 ||
    input.neutrality < 0.95 ||
    input.languageQuality < 0.95;

  if (belowGate && (!input.findingNote || input.findingNote.trim().length < 5)) {
    return {
      valid: false,
      error:
        "A finding note (at least 5 characters) is required when any QA rubric dimension is below the launch gate",
      compositeScore,
      requiresDiscrepancyTicket: true,
    };
  }
  return {
    valid: true,
    error: null,
    compositeScore,
    requiresDiscrepancyTicket: belowGate,
  };
}

export interface AuditorDriftAndFairnessInput {
  readonly intentMixKlDivergence: number;
  readonly abstentionRate24h: number;
  readonly guardrailTriggerRate24h: number;
  readonly accuracyByLocale: Readonly<Record<string, number>>;
}

/**
 * Build the Section 14.2 Online Drift Monitors & Language Parity Gap view for `ssra_auditor`.
 */
export function buildAuditorDriftAndFairnessView(input: AuditorDriftAndFairnessInput) {
  const enScore = input.accuracyByLocale.en ?? 1.0;
  let maxGap = 0;
  const breachedLocales: string[] = [];

  for (const [loc, score] of Object.entries(input.accuracyByLocale)) {
    if (!Number.isFinite(score)) {
      breachedLocales.push(loc);
      maxGap = 1.0;
      continue;
    }
    const gap = Math.max(0, Math.round((enScore - score) * 10000) / 10000);
    if (gap > maxGap) {
      maxGap = gap;
    }
    if (gap > 0.05) {
      breachedLocales.push(loc);
    }
  }

  const driftBreached =
    !Number.isFinite(input.intentMixKlDivergence) ||
    !Number.isFinite(input.abstentionRate24h) ||
    !Number.isFinite(input.guardrailTriggerRate24h) ||
    input.intentMixKlDivergence > 0.15 ||
    input.abstentionRate24h > 0.25 ||
    input.guardrailTriggerRate24h > 0.05;

  const healthy = !driftBreached && breachedLocales.length === 0;
  return {
    bannerRole: healthy ? ("status" as const) : ("alert" as const),
    status: healthy ? ("HEALTHY" as const) : ("DRIFT_OR_PARITY_ALERT" as const),
    maxLanguageParityGapPct: Math.round(maxGap * 1000) / 10,
    breachedLocales,
    driftBreached,
  };
}

/**
 * Build an ISO/IEC 42001 Clause 9.2 & EU AI Act Art. 12 Cryptographic Audit Evidence Package,
 * blocking export if the WORM hash chain or Merkle seal is broken.
 */
export function buildAuditorEvidencePackage(params: {
  readonly auditReport: AuditVerificationReport;
  readonly snapshotVersion: string;
  readonly sampledThreadIds: readonly string[];
  readonly qaCompositeScore: number;
}) {
  const trailView = buildAuditorTrailIntegrityView(params.auditReport, {
    role: "ssra_auditor",
  });
  if (trailView.chipText === "Record altered") {
    return {
      exportAllowed: false,
      blockedReason: trailView.explanation,
      bundle: null,
    };
  }
  return {
    exportAllowed: true,
    blockedReason: null,
    bundle: {
      standard: "ISO/IEC 42001:2023 + NIST AI 600-1 + EU AI Act Art. 12",
      headHash: params.auditReport.head_hash,
      snapshotVersion: params.snapshotVersion,
      sampledThreadIds: [...params.sampledThreadIds],
      qaCompositeScore: params.qaCompositeScore,
    },
  };
}
