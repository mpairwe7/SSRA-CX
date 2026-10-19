import { describe, expect, it } from "vitest";
import {
  checkPerformanceBudgets,
  createBrowserTraceparent,
  isValidW3cTraceparent,
} from "../src/index.js";

describe("@ssra/telemetry performance budget gates", () => {
  it("enforces Section 9.5 low-end Android & 150 KB gzip JS budgets", () => {
    const ok = checkPerformanceBudgets({
      firstLoadJsGzipKb: 112,
      lcpMs: 1850,
      inpMs: 120,
      cls: 0.03,
    });
    expect(ok.passed).toBe(true);

    const bloated = checkPerformanceBudgets({
      firstLoadJsGzipKb: 180,
      lcpMs: 3100,
      inpMs: 150,
      cls: 0.05,
      webTtftP95Ms: 1950,
    });
    expect(bloated.passed).toBe(false);
    expect(bloated.violations).toHaveLength(3);

    const nanSample = checkPerformanceBudgets({
      firstLoadJsGzipKb: Number.NaN,
      lcpMs: 1000,
      inpMs: 100,
      cls: 0.01,
    });
    expect(nanSample.passed).toBe(false);

    const tp = createBrowserTraceparent();
    expect(isValidW3cTraceparent(tp)).toBe(true);
    expect(createBrowserTraceparent(tp)).toBe(tp);
    expect(isValidW3cTraceparent("invalid-tp")).toBe(false);
  });
});
