/**
 * Performance budget and OpenTelemetry W3C traceparent helpers (Sections 9.5, 13, 14.3).
 */

export const PERFORMANCE_BUDGETS = {
  maxFirstLoadJsGzipKb: 150,
  targetFirstLoadJsGzipKb: 120,
  maxLcpMs: 2500,
  maxInpMs: 200,
  maxCls: 0.1,
  maxWebTtftP95Ms: 1500,
} as const;

export interface WebVitalsSample {
  readonly firstLoadJsGzipKb: number;
  readonly lcpMs: number;
  readonly inpMs: number;
  readonly cls: number;
  readonly webTtftP95Ms?: number;
}

export function checkPerformanceBudgets(sample: WebVitalsSample): {
  readonly passed: boolean;
  readonly violations: string[];
} {
  const violations: string[] = [];
  if (
    !Number.isFinite(sample.firstLoadJsGzipKb) ||
    sample.firstLoadJsGzipKb < 0 ||
    sample.firstLoadJsGzipKb > PERFORMANCE_BUDGETS.maxFirstLoadJsGzipKb
  ) {
    violations.push(
      `firstLoadJsGzipKb ${sample.firstLoadJsGzipKb} > ${PERFORMANCE_BUDGETS.maxFirstLoadJsGzipKb}`,
    );
  }
  if (
    !Number.isFinite(sample.lcpMs) ||
    sample.lcpMs < 0 ||
    sample.lcpMs > PERFORMANCE_BUDGETS.maxLcpMs
  ) {
    violations.push(`lcpMs ${sample.lcpMs} > ${PERFORMANCE_BUDGETS.maxLcpMs}`);
  }
  if (
    !Number.isFinite(sample.inpMs) ||
    sample.inpMs < 0 ||
    sample.inpMs > PERFORMANCE_BUDGETS.maxInpMs
  ) {
    violations.push(`inpMs ${sample.inpMs} > ${PERFORMANCE_BUDGETS.maxInpMs}`);
  }
  if (!Number.isFinite(sample.cls) || sample.cls < 0 || sample.cls > PERFORMANCE_BUDGETS.maxCls) {
    violations.push(`cls ${sample.cls} > ${PERFORMANCE_BUDGETS.maxCls}`);
  }
  if (
    sample.webTtftP95Ms !== undefined &&
    (!Number.isFinite(sample.webTtftP95Ms) ||
      sample.webTtftP95Ms < 0 ||
      sample.webTtftP95Ms > PERFORMANCE_BUDGETS.maxWebTtftP95Ms)
  ) {
    violations.push(`webTtftP95Ms ${sample.webTtftP95Ms} > ${PERFORMANCE_BUDGETS.maxWebTtftP95Ms}`);
  }
  return {
    passed: violations.length === 0,
    violations,
  };
}

const W3C_TRACEPARENT_PATTERN = /^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$/;

export function isValidW3cTraceparent(candidate: string): boolean {
  const m = W3C_TRACEPARENT_PATTERN.exec(candidate.trim().toLowerCase());
  if (!m) {
    return false;
  }
  return m[1] !== "0".repeat(32) && m[2] !== "0".repeat(16);
}

export function createBrowserTraceparent(existing?: string): string {
  if (existing && isValidW3cTraceparent(existing)) {
    return existing.trim().toLowerCase();
  }
  const bytes = new Uint8Array(24);
  globalThis.crypto.getRandomValues(bytes);
  const hex = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `00-${hex.slice(0, 32)}-${hex.slice(32, 48)}-01`;
}
