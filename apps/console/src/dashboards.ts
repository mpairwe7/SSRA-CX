/**
 * Staff Console Dashboards (`apps/console/src/dashboards.ts`):
 * - Analytics Dashboard (`buildAnalyticsDashboardView` — `analytics/page.tsx` pattern)
 * - Answer Evaluation Dashboard (`buildEvaluationDashboardView` — `analytics/evaluation/page.tsx` pattern)
 * - Service Quality Audit Overview (`buildQualityAuditOverview`, `pointsHint`, `aiCallsHeadline`, `evaluateAuthorityStatusResponse` — `admin/page.tsx` pattern)
 * - Tax Agent One-Case-at-a-Time Queue Workbench (`buildAgentQueueWorkbench`, `waitTone`, `waitingFor`, `ticketRef` — `agent/page.tsx` & `ticketUi.ts` pattern)
 */

import {
  buildOpsPageShell,
  buildOpsStatTile,
  EVAL_METRIC_PLAIN_LABELS,
  type OpsPageShellDescriptor,
  type OpsStatTileDescriptor,
  plainSeconds,
  QUANTILE_PLAIN_LABELS,
  toDelta,
} from "./views.js";

export const SLA_WARN_SECONDS = 4 * 3600;
export const SLA_BREACH_SECONDS = 24 * 3600;
export const NEEDS_REVIEW_SHOWN = 6;

export type WaitTone = "ok" | "warn" | "breach";
export type QueueTab = "next" | "mine" | "resolved";

export const PRIORITY_RANK: Record<string, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
};

export interface TicketQueueItem {
  readonly id: string;
  readonly status: "open" | "assigned" | "resolved" | "wontfix";
  readonly priority: "urgent" | "high" | "normal" | "low";
  readonly created_at: number;
  readonly first_response_at?: number | null | undefined;
  readonly reply_at?: number | null | undefined;
  readonly assignee?: string | null | undefined;
  readonly locale?: string | undefined;
  readonly modality?: string | undefined;
}

export function waitingSeconds(createdAt: number, nowMs = Date.now()): number {
  return Math.max(0, nowMs / 1000 - createdAt);
}

export function waitingFor(createdAt: number, nowMs = Date.now()): string {
  const seconds = waitingSeconds(createdAt, nowMs);
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  return h ? `${d}d ${h}h` : `${d}d`;
}

export const SLA_THRESHOLDS_BY_PRIORITY: Readonly<
  Record<
    TicketQueueItem["priority"],
    { readonly warnSeconds: number; readonly breachSeconds: number }
  >
> = {
  urgent: { warnSeconds: 3600, breachSeconds: 2 * 3600 },
  high: { warnSeconds: 2 * 3600, breachSeconds: 4 * 3600 },
  normal: { warnSeconds: SLA_WARN_SECONDS, breachSeconds: SLA_BREACH_SECONDS },
  low: { warnSeconds: 12 * 3600, breachSeconds: 48 * 3600 },
};

/**
 * Compute SLA wait tone (`ok`, `warn`, `breach`) from ticket age and priority thresholds.
 */
export function waitTone(
  createdAt: number,
  firstResponseAt?: number | null,
  replyAt?: number | null,
  nowMs = Date.now(),
  status: TicketQueueItem["status"] = "open",
  priority: TicketQueueItem["priority"] = "normal",
): WaitTone {
  if (status === "resolved" || status === "wontfix") {
    return "ok";
  }
  const lastTouch = firstResponseAt ? replyAt || firstResponseAt : null;
  const age = lastTouch ? Math.max(0, nowMs / 1000 - lastTouch) : waitingSeconds(createdAt, nowMs);
  const thresholds = SLA_THRESHOLDS_BY_PRIORITY[priority] ?? SLA_THRESHOLDS_BY_PRIORITY.normal;
  if (age >= thresholds.breachSeconds) return "breach";
  if (age >= thresholds.warnSeconds) return "warn";
  return "ok";
}

export function ticketRef(ticketId: string): string {
  if (!ticketId) return "";
  const clean = ticketId.replace(/^#+/, "").replace(/^TIC-/i, "");
  return `TIC-${clean.slice(0, 8).toUpperCase()}`;
}

export function sortQueue(items: readonly TicketQueueItem[]): TicketQueueItem[] {
  return [...items].sort((a, b) => {
    const pa = PRIORITY_RANK[a.priority] ?? 2;
    const pb = PRIORITY_RANK[b.priority] ?? 2;
    if (pa !== pb) return pa - pb;
    return a.created_at - b.created_at;
  });
}

export interface AgentQueueViewState {
  readonly status: "open" | "assigned" | "resolved";
  readonly mine: boolean;
  readonly ticket: string | null;
}

/**
 * Claiming a case pins `ticket` first and transitions to `{ status: "assigned", mine: true, ticket: id }`
 * so the right-hand case pane never silently swaps to the next taxpayer's case when `id` leaves `Next up`.
 */
export function buildAgentQueueWorkbench(params: {
  readonly tickets: readonly TicketQueueItem[];
  readonly view: AgentQueueViewState;
  readonly officerHandle: string;
  readonly nowMs?: number | undefined;
  readonly viewportWidthPx?: number | undefined;
}) {
  const nowMs = params.nowMs ?? Date.now();
  const openedId = params.view.ticket;
  let rows = sortQueue(params.tickets);
  if (params.view.status === "resolved") {
    rows = rows.filter(
      (t) => t.status === "resolved" || t.status === "wontfix" || t.id === openedId,
    );
  } else if (params.view.mine) {
    rows = rows.filter(
      (t) =>
        (t.assignee === params.officerHandle &&
          t.status !== "resolved" &&
          t.status !== "wontfix") ||
        t.id === openedId,
    );
  } else {
    rows = rows.filter((t) => t.status === "open" || t.status === "assigned" || t.id === openedId);
  }
  const activeId =
    openedId && rows.some((r) => r.id === openedId) ? openedId : (rows[0]?.id ?? null);
  const urgentCount = rows.filter((t) => t.priority === "urgent").length;
  const breachingCount = rows.filter(
    (t) =>
      waitTone(t.created_at, t.first_response_at, t.reply_at, nowMs, t.status, t.priority) ===
      "breach",
  ).length;
  const isCompactViewport =
    params.viewportWidthPx !== undefined && Number.isFinite(params.viewportWidthPx)
      ? params.viewportWidthPx < 768
      : false;
  const mobileActivePane: "queue_list" | "case_detail" | "split_both" = !isCompactViewport
    ? "split_both"
    : openedId
      ? "case_detail"
      : "queue_list";

  return {
    tab: (params.view.status === "resolved"
      ? "resolved"
      : params.view.mine
        ? "mine"
        : "next") as QueueTab,
    rows,
    openedId,
    activeId,
    urgentCount,
    breachingCount,
    isCompactViewport,
    mobileActivePane,
    hotkeys: ["j/k: navigate", "a: assign to me", "r: focus reply"] as const,
    claimCaseTransition: (claimId: string): AgentQueueViewState => ({
      status: "assigned",
      mine: true,
      ticket: claimId,
    }),
  };
}

export interface AgentQueueHotkeyAction {
  readonly handled: boolean;
  readonly action: "none" | "select_ticket" | "assign_to_me" | "focus_reply";
  readonly targetTicketId: string | null;
}

/**
 * Resolve keyboard-first triage shortcuts (`j`, `k`, `a`, `r`) for the Staff Queue Workbench,
 * ignoring keystrokes while the officer is typing inside a text input or textarea.
 */
export function resolveAgentQueueHotkey(params: {
  readonly key: string;
  readonly rows: readonly TicketQueueItem[];
  readonly activeId: string | null;
  readonly isTypingInInput?: boolean | undefined;
}): AgentQueueHotkeyAction {
  if (params.isTypingInInput || params.rows.length === 0) {
    return { handled: false, action: "none", targetTicketId: params.activeId };
  }
  const currentIdx = Math.max(
    0,
    params.rows.findIndex((r) => r.id === params.activeId),
  );
  const activeTicket = params.rows[currentIdx] ?? params.rows[0];
  if (!activeTicket) {
    return { handled: false, action: "none", targetTicketId: null };
  }
  switch (params.key) {
    case "j": {
      const next = params.rows[Math.min(params.rows.length - 1, currentIdx + 1)] ?? activeTicket;
      return { handled: true, action: "select_ticket", targetTicketId: next.id };
    }
    case "k": {
      const prev = params.rows[Math.max(0, currentIdx - 1)] ?? activeTicket;
      return { handled: true, action: "select_ticket", targetTicketId: prev.id };
    }
    case "a":
      return { handled: true, action: "assign_to_me", targetTicketId: activeTicket.id };
    case "r":
      return { handled: true, action: "focus_reply", targetTicketId: activeTicket.id };
    default:
      return { handled: false, action: "none", targetTicketId: activeTicket.id };
  }
}

export function pointsHint(
  now: number | null | undefined,
  before: number | null | undefined,
): string {
  if (now == null || before == null || !Number.isFinite(now) || !Number.isFinite(before)) {
    return "nothing to compare in the period before";
  }
  const change = Math.round((now - before) * 10) / 10;
  if (change === 0) return `unchanged from ${before}% in the period before`;
  return `${change > 0 ? "up" : "down"} ${Math.abs(change)} points from ${before}% in the period before`;
}

export interface RatingsHeadlineMoment {
  readonly asked: number;
  readonly answered: number;
  readonly positive: number;
  readonly previousAnswered?: number | undefined;
  readonly previousPositivePct?: number | undefined;
}

function share(part: number, whole: number): number | null {
  return whole > 0 ? Math.round((part / whole) * 1000) / 10 : null;
}

/**
 * Combine `end` and `transfer` call rating moments weighted by `answered` count.
 */
export function aiCallsHeadline(moments: readonly RatingsHeadlineMoment[]) {
  const asked = moments.reduce((n, m) => n + m.asked, 0);
  const answered = moments.reduce((n, m) => n + m.answered, 0);
  const positive = moments.reduce((n, m) => n + m.positive, 0);
  const prevAnswered = moments.reduce((n, m) => n + (m.previousAnswered ?? 0), 0);
  const prevPositive = moments.reduce(
    (n, m) => n + Math.round(((m.previousPositivePct ?? 0) * (m.previousAnswered ?? 0)) / 100),
    0,
  );
  return {
    asked,
    answered,
    positivePct: share(positive, answered),
    previousPositivePct: share(prevPositive, prevAnswered),
  };
}

/**
 * Guard `/api/v1/authority/status`: never parse an HTTP 401/403 JSON error body
 * as `{ fresh: undefined }` ("Stale or missing" corpus alarm).
 */
export function evaluateAuthorityStatusResponse(
  httpStatus: number,
  body: {
    readonly fresh?: boolean;
    readonly sources_checked?: number;
    readonly version?: string;
  } | null,
): {
  readonly state: "FRESH" | "STALE_OR_MISSING" | "AUTH_OR_HTTP_ERROR";
  readonly sourcesCheckedText: string;
} {
  if (httpStatus < 200 || httpStatus >= 300 || !body) {
    return { state: "AUTH_OR_HTTP_ERROR", sourcesCheckedText: "—" };
  }
  return {
    state: body.fresh ? "FRESH" : "STALE_OR_MISSING",
    sourcesCheckedText:
      typeof body.sources_checked === "number" ? String(body.sources_checked) : "—",
  };
}

export interface AnalyticsDashboardView {
  readonly shell: OpsPageShellDescriptor;
  readonly liveGauges: readonly OpsStatTileDescriptor[];
  readonly ciVerifiedTargets: readonly OpsStatTileDescriptor[];
  readonly replicaLifetimeTile: OpsStatTileDescriptor;
}

export function buildAnalyticsDashboardView(params: {
  readonly p95TtftMs: number;
  readonly previousP95TtftMs?: number | undefined;
  readonly containmentRatePct: number;
  readonly citationPrecisionPct: number;
  readonly replicaUptimeHours: number;
}): AnalyticsDashboardView {
  const shell = buildOpsPageShell({
    eyebrow: "Observe",
    title: "Service analytics & SLOs",
    description:
      "Plain-language supervisor observability across Web, WhatsApp, SMS, USSD, and Voice",
    provenance: "LIVE_TELEMETRY",
    allMetricsPassed: params.p95TtftMs <= 1500 && params.citationPrecisionPct >= 98,
  });

  const liveGauges: OpsStatTileDescriptor[] = [
    buildOpsStatTile({
      label: QUANTILE_PLAIN_LABELS.p95,
      technicalSubtitle: "Chat p95 TTFT (target <= 1.5s)",
      formattedValue: plainSeconds(params.p95TtftMs),
      provenance: "LIVE_TELEMETRY",
      scope: "WINDOW_SCOPED",
      delta: toDelta(params.p95TtftMs, params.previousP95TtftMs),
      higherIsBetter: false,
    }),
    buildOpsStatTile({
      label: "Questions resolved without needing an officer",
      technicalSubtitle: "Quality-adjusted containment rate",
      formattedValue: `${params.containmentRatePct}%`,
      provenance: "LIVE_TELEMETRY",
      scope: "WINDOW_SCOPED",
      higherIsBetter: true,
    }),
    buildOpsStatTile({
      label: EVAL_METRIC_PLAIN_LABELS.citation_precision?.plainLabel ?? "Verified legal citations",
      technicalSubtitle: "citation_precision (gate >= 98%)",
      formattedValue: `${params.citationPrecisionPct}%`,
      provenance: "LIVE_TELEMETRY",
      scope: "WINDOW_SCOPED",
      higherIsBetter: true,
    }),
  ];

  const ciVerifiedTargets: OpsStatTileDescriptor[] = [
    buildOpsStatTile({
      label: "Availability SLO target",
      technicalSubtitle: "Verified by multi-window burn-rate alerts",
      formattedValue: "99.9%",
      provenance: "CI_VERIFIED_TARGET",
      scope: "WINDOW_SCOPED",
    }),
    buildOpsStatTile({
      label: "WCAG 2.2 AA accessibility gate",
      technicalSubtitle: "Verified in CI (verify_frontend_budgets_and_a11y.py)",
      formattedValue: "100%",
      provenance: "CI_VERIFIED_TARGET",
      scope: "WINDOW_SCOPED",
    }),
    buildOpsStatTile({
      label: "Backend PEP 669 test coverage gate",
      technicalSubtitle: "Verified in CI (check_coverage_gate.py >= 98%)",
      formattedValue: "98.1%",
      provenance: "CI_VERIFIED_TARGET",
      scope: "WINDOW_SCOPED",
    }),
  ];

  const replicaLifetimeTile = buildOpsStatTile({
    label: "Current container uptime",
    technicalSubtitle: "Replica process lifetime (does not change with period picker)",
    formattedValue: `${params.replicaUptimeHours} hours`,
    provenance: "LIVE_TELEMETRY",
    scope: "REPLICA_LIFETIME",
  });

  return {
    shell,
    liveGauges,
    ciVerifiedTargets,
    replicaLifetimeTile,
  };
}

export interface EvalMetricItem {
  readonly name: string;
  readonly value: number;
  readonly threshold: number;
  readonly passed: boolean;
}

export function buildEvaluationDashboardView(params: {
  readonly liveEvalMetrics: readonly EvalMetricItem[] | null;
  readonly staticFallbackMetrics: readonly EvalMetricItem[];
}) {
  const isLive = Boolean(params.liveEvalMetrics && params.liveEvalMetrics.length > 0);
  const activeMetrics =
    isLive && params.liveEvalMetrics ? params.liveEvalMetrics : params.staticFallbackMetrics;
  const allPass = activeMetrics.length > 0 && activeMetrics.every((m) => m.passed);
  const shell = buildOpsPageShell({
    eyebrow: "Observe",
    title: "Answer evaluation",
    description: "RAG groundedness, numeric provenance, and OWASP ASI01-ASI10 red-team gates",
    provenance: isLive ? "LIVE_TELEMETRY" : "ILLUSTRATIVE_FALLBACK",
    allMetricsPassed: allPass,
  });

  const rows = activeMetrics.map((m) => ({
    plainQuestion: EVAL_METRIC_PLAIN_LABELS[m.name]?.plainLabel ?? m.name,
    technicalKey: m.name,
    valuePct: `${Math.round(m.value * 100)}%`,
    thresholdPct: `${Math.round(m.threshold * 100)}%`,
    passed: m.passed,
  }));

  return {
    shell,
    isLive,
    rows,
  };
}
