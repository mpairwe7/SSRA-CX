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
}

export function checkPerformanceBudgets(sample: WebVitalsSample): {
  readonly passed: boolean;
  readonly violations: string[];
} {
  const violations: string[] = [];
  if (sample.firstLoadJsGzipKb > PERFORMANCE_BUDGETS.maxFirstLoadJsGzipKb) {
    violations.push(
      `firstLoadJsGzipKb ${sample.firstLoadJsGzipKb} > ${PERFORMANCE_BUDGETS.maxFirstLoadJsGzipKb}`,
    );
  }
  if (sample.lcpMs > PERFORMANCE_BUDGETS.maxLcpMs) {
    violations.push(`lcpMs ${sample.lcpMs} > ${PERFORMANCE_BUDGETS.maxLcpMs}`);
  }
  if (sample.inpMs > PERFORMANCE_BUDGETS.maxInpMs) {
    violations.push(`inpMs ${sample.inpMs} > ${PERFORMANCE_BUDGETS.maxInpMs}`);
  }
  if (sample.cls > PERFORMANCE_BUDGETS.maxCls) {
    violations.push(`cls ${sample.cls} > ${PERFORMANCE_BUDGETS.maxCls}`);
  }
  return {
    passed: violations.length === 0,
    violations,
  };
}
