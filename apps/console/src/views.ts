/**
 * Phase 3 & 4 Staff Console Interactive View Models, Honest Telemetry Provenance,
 * Plain-Language Supervisor Layer & Trend Arithmetic (`apps/console/src/views.ts` — Section 3, 7, 9.2, 13, 14).
 *
 * Standards:
 * - ISO/IEC 25010:2023 §4 (Interaction Capability)
 * - EU AI Act Art. 13 (Transparency) & ISO/IEC 42001 §9.1 (Monitoring)
 * - NIST AI RMF MEASURE 2.6 (Evaluation Evidence Provenance)
 */

import { authorizeConsoleAccess, type ConsoleSession, KNOWLEDGE_RELEASE_STEPS } from "./proxy.js";

export type TelemetryProvenance = "LIVE_TELEMETRY" | "CI_VERIFIED_TARGET" | "ILLUSTRATIVE_FALLBACK";

export type TelemetryScope = "WINDOW_SCOPED" | "REPLICA_LIFETIME";

export interface CopilotDraftReviewAction {
  readonly conversationId: string;
  readonly staffId: string;
  readonly decision: "APPROVE_AND_SEND" | "EDIT_AND_SEND" | "REJECT_AND_WRITE_MANUAL";
  readonly citationsIncluded: readonly string[];
}

export function validateCopilotDraftApproval(
  session: ConsoleSession | null,
  action: CopilotDraftReviewAction,
): { readonly valid: boolean; readonly error?: string } {
  const auth = authorizeConsoleAccess(session);
  if (!auth.allowed) {
    return { valid: false, error: auth.reason ?? "UNAUTHORIZED" };
  }
  if (action.decision === "APPROVE_AND_SEND" && action.citationsIncluded.length === 0) {
    return {
      valid: false,
      error: "PRINCIPLE_1_GROUNDED_OR_SILENT_CITATIONS_REQUIRED",
    };
  }
  return { valid: true };
}

export function buildKnowledgeReleasePipelineView(currentStepIndex: number) {
  return KNOWLEDGE_RELEASE_STEPS.map((step, idx) => ({
    step,
    state:
      idx < currentStepIndex
        ? ("COMPLETED" as const)
        : idx === currentStepIndex
          ? ("ACTIVE" as const)
          : ("PENDING" as const),
  }));
}

const DATE_FMT_GB = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeZone: "Africa/Juba",
});

/**
 * Crash-safe date formatter: `Intl.DateTimeFormat().format(NaN)` throws RangeError,
 * which previously took down the entire analytics route on missing `updated_at`.
 */
export function formatSafeTimestamp(seconds: number | undefined | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const ms = seconds * 1000;
  if (!Number.isFinite(ms)) return "—";
  return DATE_FMT_GB.format(ms);
}

/**
 * Plain-language supervisor duration formatting ("850 milliseconds" or "1.4 seconds").
 */
export function plainSeconds(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} milliseconds`;
  const seconds = ms / 1000;
  return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} seconds`;
}

export const QUANTILE_PLAIN_LABELS = {
  p50: "Half are faster",
  p95: "19 in 20 are faster",
  p99: "99 in 100 are faster",
} as const;

export const EVAL_METRIC_PLAIN_LABELS: Record<
  string,
  { readonly plainLabel: string; readonly technicalKey: string }
> = {
  numeric_accuracy: {
    plainLabel: "Zero fabricated tax figures",
    technicalKey: "numeric_accuracy",
  },
  citation_precision: {
    plainLabel: "Every legal citation resolves to an approved SSRA document",
    technicalKey: "citation_precision",
  },
  faithfulness: {
    plainLabel: "Sticks strictly to retrieved SSRA documents",
    technicalKey: "faithfulness",
  },
  abstention_precision: {
    plainLabel: "Hands off out-of-scope or T4 questions to an officer",
    technicalKey: "abstention_precision",
  },
};

const MEASURE_RE = /^([-+]?\d+(?:[., ]\d+)*)(\s*)([^\d\s].*)$/;

/**
 * Split "850 milliseconds" into `{ figure, gap, unit }` so the unit can be rendered
 * smaller in `.ops-stat-unit` without altering `textContent` or shrinking compound
 * durations like "1d 8h 55m".
 */
export function splitMeasureParts(value: string): {
  readonly figure: string;
  readonly gap: string;
  readonly unit: string | null;
} {
  const match = MEASURE_RE.exec(value);
  if (!match) {
    return { figure: value, gap: "", unit: null };
  }
  const [, figure = value, gap = "", unit = ""] = match;
  if (/\d/.test(unit)) {
    return { figure: value, gap: "", unit: null };
  }
  return { figure, gap, unit };
}

export interface TrendDelta {
  readonly value: number;
  readonly previous: number;
  readonly change: number;
  readonly ratio: number | null;
  readonly direction: "up" | "down" | "flat";
}

export function previousWindow(current?: number, doubleWindow?: number): number | undefined {
  if (
    current == null ||
    doubleWindow == null ||
    !Number.isFinite(current) ||
    !Number.isFinite(doubleWindow)
  ) {
    return undefined;
  }
  return Math.max(0, doubleWindow - current);
}

export function toDelta(value?: number, previous?: number): TrendDelta | undefined {
  if (value == null || previous == null || !Number.isFinite(value) || !Number.isFinite(previous)) {
    return undefined;
  }
  const change = value - previous;
  return {
    value,
    previous,
    change,
    ratio: previous === 0 ? null : change / previous,
    direction: change > 0 ? "up" : change < 0 ? "down" : "flat",
  };
}

export function formatDelta(delta: TrendDelta): string {
  if (delta.direction === "flat") return "no change";
  const sign = delta.change > 0 ? "+" : "−";
  const magnitude = Math.abs(delta.change);
  if (delta.ratio == null) return `${sign}${magnitude}`;
  return `${sign}${Math.abs(Math.round(delta.ratio * 100))}%`;
}

export interface OpsStatTileDescriptor {
  readonly label: string;
  readonly technicalSubtitle: string;
  readonly figure: string;
  readonly unit: string | null;
  readonly provenance: TelemetryProvenance;
  readonly scope: TelemetryScope;
  readonly deltaText: string | null;
  readonly semanticDeltaClass: "" | "is-good" | "is-bad";
}

export function buildOpsStatTile(params: {
  readonly label: string;
  readonly technicalSubtitle: string;
  readonly formattedValue: string;
  readonly provenance: TelemetryProvenance;
  readonly scope: TelemetryScope;
  readonly delta?: TrendDelta | undefined;
  readonly higherIsBetter?: boolean | undefined;
}): OpsStatTileDescriptor {
  const parts = splitMeasureParts(params.formattedValue);
  let semanticDeltaClass: "" | "is-good" | "is-bad" = "";
  if (params.delta && params.delta.direction !== "flat" && params.higherIsBetter !== undefined) {
    const isGood = params.delta.direction === "up" ? params.higherIsBetter : !params.higherIsBetter;
    semanticDeltaClass = isGood ? "is-good" : "is-bad";
  }
  return {
    label: params.label,
    technicalSubtitle: params.technicalSubtitle,
    figure: parts.figure,
    unit: parts.unit ? `${parts.gap}${parts.unit}` : null,
    provenance: params.provenance,
    scope: params.scope,
    deltaText: params.delta ? formatDelta(params.delta) : null,
    semanticDeltaClass,
  };
}

export interface OpsPageShellDescriptor {
  readonly mainId: "staff-main";
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly provenanceBanner: string | null;
  readonly allGatesPassClaimAllowed: boolean;
}

/**
 * Unified Operations Page Shell (`OpsPage` pattern): never claims "ALL GATES PASS"
 * when backed by illustrative fallback data rather than a live evaluation run.
 */
export function buildOpsPageShell(params: {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly provenance: TelemetryProvenance;
  readonly allMetricsPassed: boolean;
}): OpsPageShellDescriptor {
  const isLive = params.provenance === "LIVE_TELEMETRY";
  return {
    mainId: "staff-main",
    eyebrow: params.eyebrow,
    title: params.title,
    description: params.description,
    provenanceBanner: isLive
      ? null
      : params.provenance === "CI_VERIFIED_TARGET"
        ? "Target verified in CI release pipeline — not a live runtime gauge."
        : "Illustrative fallback sample — run `task eval` or connect live telemetry for measured evidence.",
    allGatesPassClaimAllowed: isLive && params.allMetricsPassed,
  };
}

export * from "./dashboards.js";
export * from "./roles-and-audit.js";
