/**
 * Administrator Control-Plane Workbenches (`apps/console/src/admin-workbench.ts` — Sections 6.4, 7, 12.3, 13):
 * - 5-Step Degradation Ladder & Kill-Switch Blast-Radius Preview (`/admin/flags`)
 * - 6-Step Knowledge Release Maker-Checker & One-Step Rollback Governance (`/admin`)
 * - System Connectors & Upstream Feature-Flag Health Matrix (`/admin/connectors`)
 * - Exact-Match Answer Override Safety Validator (`/admin/overrides`)
 */

import type { StaffRole } from "./roles-and-audit.js";

export type DegradationLevel = 1 | 2 | 3 | 4 | 5;

export const DEGRADATION_STEP_LABELS: Readonly<Record<DegradationLevel, string>> = {
  1: "Level 1 — Primary Sovereign vLLM (Sunbird/Sunflower-Qwen3.5-9B)",
  2: "Level 2 — Secondary Sovereign vLLM (Qwen/Qwen3-8B)",
  3: "Level 3 — Self-Hosted CPU Quantized Fallback",
  4: "Level 4 — Retrieval-Only Cited Answer Cards + Deterministic Calculators",
  5: "Level 5 — Static Approved FAQs + Officer Callback Intake",
};

export interface KillSwitchControlPlaneView {
  readonly currentLevel: DegradationLevel;
  readonly modeLabel: string;
  readonly llmGenerationActive: boolean;
  readonly deterministicCalculatorsActive: true;
  readonly pausedChannels: readonly string[];
  readonly disabledToolsCount: number;
  readonly canApplyMutation: boolean;
  readonly disabledReason: string | null;
}

/**
 * Build the `/admin/flags` 5-Step Degradation Ladder & Kill-Switch blast-radius preview,
 * gating mutations on `role === "ssra_admin"` and active JIT elevation (`jitActive === true`).
 */
export function buildKillSwitchControlPlaneView(params: {
  readonly role: StaffRole;
  readonly jitActive: boolean;
  readonly degradationLevel: DegradationLevel;
  readonly disabledTools: readonly string[];
  readonly disabledChannels: readonly string[];
}): KillSwitchControlPlaneView {
  const canApply = params.role === "ssra_admin" && params.jitActive;
  const disabledReason =
    params.role !== "ssra_admin"
      ? "Only administrators may modify degradation levels or kill switches."
      : !params.jitActive
        ? "Active Just-In-Time (JIT) admin elevation is required to modify kill switches."
        : null;

  return {
    currentLevel: params.degradationLevel,
    modeLabel: DEGRADATION_STEP_LABELS[params.degradationLevel],
    llmGenerationActive: params.degradationLevel <= 3,
    deterministicCalculatorsActive: true,
    pausedChannels: [...params.disabledChannels],
    disabledToolsCount: params.disabledTools.length,
    canApplyMutation: canApply,
    disabledReason,
  };
}

export interface KnowledgeReleaseGovernanceView {
  readonly version: string;
  readonly status: "DRAFT" | "LEGAL_REVIEW" | "APPROVED" | "PUBLISHED" | "ROLLED_BACK";
  readonly canApproveLegal: boolean;
  readonly canPublish: boolean;
  readonly canRollback: boolean;
  readonly autoRollbackTriggered: boolean;
  readonly governanceNote: string;
}

/**
 * Build the 6-Step Knowledge Release governance control state, enforcing maker-checker separation
 * (`draftAuthorId !== currentStaffId`), evaluation regression gates, and 1-step rollback.
 */
export function buildKnowledgeReleaseGovernanceView(params: {
  readonly version: string;
  readonly status: "DRAFT" | "LEGAL_REVIEW" | "APPROVED" | "PUBLISHED" | "ROLLED_BACK";
  readonly draftAuthorId: string;
  readonly currentStaffId: string;
  readonly role: StaffRole;
  readonly evalRegressionPassed: boolean;
}): KnowledgeReleaseGovernanceView {
  const isAdmin = params.role === "ssra_admin";
  const isSelfAuthor = params.draftAuthorId === params.currentStaffId;
  const canApproveLegal = isAdmin && params.status === "LEGAL_REVIEW" && !isSelfAuthor;
  const canPublish = isAdmin && params.status === "APPROVED" && params.evalRegressionPassed;
  const autoRollbackTriggered = params.status === "APPROVED" && !params.evalRegressionPassed;

  const governanceNote =
    isSelfAuthor && params.status === "LEGAL_REVIEW"
      ? "Maker-checker rule: the snapshot author cannot approve their own legal review."
      : autoRollbackTriggered
        ? "Evaluation regression gate failed — automatic 1-step rollback to previous PUBLISHED snapshot triggered."
        : `Snapshot ${params.version} is in ${params.status} state.`;

  return {
    version: params.version,
    status: autoRollbackTriggered ? "ROLLED_BACK" : params.status,
    canApproveLegal,
    canPublish,
    canRollback: isAdmin,
    autoRollbackTriggered,
    governanceNote,
  };
}

export interface ConnectorStatusRow {
  readonly id: "etax" | "ecustoms" | "boss_fx";
  readonly label: string;
  readonly mode: "LIVE" | "MOCK_SYNTHETIC_OQ002";
  readonly circuitState: "CLOSED" | "HALF_OPEN" | "OPEN";
  readonly t3WritesEnabled: boolean;
  readonly openQuestionRef: string | null;
}

/**
 * Build the `/admin/connectors` health & feature-flag matrix for e-Tax, e-Customs (`OQ-002`), and BoSS FX.
 */
export function buildSystemConnectorsHealthView(params: {
  readonly etaxCircuit: "CLOSED" | "HALF_OPEN" | "OPEN";
  readonly ecustomsCircuit: "CLOSED" | "HALF_OPEN" | "OPEN";
  readonly bossCircuit: "CLOSED" | "HALF_OPEN" | "OPEN";
  readonly t3PaymentRefEnabled?: boolean | undefined;
  readonly t3RequestTccEnabled?: boolean | undefined;
}): {
  readonly connectors: readonly ConnectorStatusRow[];
  readonly allHealthy: boolean;
} {
  const connectors: ConnectorStatusRow[] = [
    {
      id: "etax",
      label: "SSRA National e-Tax Portal (etax.nra.gov.ss)",
      mode: "LIVE",
      circuitState: params.etaxCircuit,
      t3WritesEnabled: Boolean(params.t3PaymentRefEnabled || params.t3RequestTccEnabled),
      openQuestionRef: "OQ-001 / OQ-006",
    },
    {
      id: "ecustoms",
      label: "SSRA e-Customs / TANCIS++ Adapter",
      mode: "MOCK_SYNTHETIC_OQ002",
      circuitState: params.ecustomsCircuit,
      t3WritesEnabled: false,
      openQuestionRef: "OQ-002",
    },
    {
      id: "boss_fx",
      label: "Bank of South Sudan (BoSS) Official FX Feed",
      mode: "LIVE",
      circuitState: params.bossCircuit,
      t3WritesEnabled: false,
      openQuestionRef: null,
    },
  ];
  return {
    connectors,
    allHealthy: connectors.every((c) => c.circuitState === "CLOSED"),
  };
}

const PROHIBITED_OVERRIDE_TEXT_PATTERN =
  /\b(?:waive\s+(?:your\s+)?penalty|penalty\s+is\s+waived|pay\s+cash\s+to)\b/i;

/**
 * Validate an administrator's exact-match Answer Override (`/admin/overrides`)
 * to ensure it cites an approved `sectionAnchor` and contains no prohibited waiver or cash claims.
 */
export function validateAdminAnswerOverride(input: {
  readonly role: StaffRole;
  readonly questionPattern: string;
  readonly overrideAnswerText: string;
  readonly sectionAnchor: string;
}): { readonly valid: boolean; readonly error: string | null } {
  if (input.role !== "ssra_admin") {
    return { valid: false, error: "ADMIN_ROLE_REQUIRED_FOR_ANSWER_OVERRIDE" };
  }
  if (!input.questionPattern.trim() || !input.overrideAnswerText.trim()) {
    return { valid: false, error: "QUESTION_AND_ANSWER_TEXT_REQUIRED" };
  }
  if (!input.sectionAnchor.trim()) {
    return { valid: false, error: "PRINCIPLE_1_SECTION_ANCHOR_CITATION_REQUIRED" };
  }
  if (PROHIBITED_OVERRIDE_TEXT_PATTERN.test(input.overrideAnswerText)) {
    return { valid: false, error: "PROHIBITED_WAIVER_OR_CASH_CLAIM_IN_OVERRIDE" };
  }
  return { valid: true, error: null };
}
