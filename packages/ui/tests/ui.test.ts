import { describe, expect, it } from "vitest";
import {
  computeJubaMonthlyFilingDeadline,
  getHtmlLayoutProps,
  getSouthSudanFiscalYear,
  SSRA_DESIGN_TOKENS,
} from "../src/index.js";

describe("@ssra/ui design tokens and RTL layout", () => {
  it("enforces WCAG 2.2 AA touch target minimum and Arabic RTL direction", () => {
    expect(SSRA_DESIGN_TOKENS.minTouchTargetPx).toBeGreaterThanOrEqual(44);
    expect(getHtmlLayoutProps("ar")).toEqual({ lang: "ar", dir: "rtl" });
    expect(getHtmlLayoutProps("en")).toEqual({ lang: "en", dir: "ltr" });
    expect(getSouthSudanFiscalYear({ year: 2026, month: 10, day: 16 })).toBe("2026/2027");
    expect(computeJubaMonthlyFilingDeadline(2026, 9, 15).dueDateIso).toBe(
      "2026-10-15T23:59:59+02:00",
    );
  });
});
