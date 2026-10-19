import { describe, expect, it } from "vitest";
import {
  buildAccessibleOtpInputProps,
  computeJubaMonthlyFilingDeadline,
  extractOfficerHours,
  formatNextShiftJuba,
  getHtmlLayoutProps,
  getSouthSudanFiscalYear,
  resolveMenuKeyNavigation,
  resolveSurfaceDesignContext,
  SSRA_DESIGN_TOKENS,
  shouldEnableLowDataMode,
} from "../src/index.js";

describe("@ssra/ui design tokens and RTL layout", () => {
  it("enforces WCAG 2.2 AA touch target minimum, SC 3.3.8 OTP autofill, and Arabic RTL direction", () => {
    expect(SSRA_DESIGN_TOKENS.minTouchTargetPx).toBeGreaterThanOrEqual(44);
    expect(SSRA_DESIGN_TOKENS.focusOutlineCss).toContain("2px solid");
    const otpAr = buildAccessibleOtpInputProps("ar");
    expect(otpAr.autoComplete).toBe("one-time-code");
    expect(otpAr.dir).toBe("ltr");
    expect(otpAr.pasteAllowed).toBe(true);
    expect(getHtmlLayoutProps("ar")).toEqual({ lang: "ar", dir: "rtl" });
    expect(getHtmlLayoutProps("en")).toEqual({ lang: "en", dir: "ltr" });
    expect(getSouthSudanFiscalYear({ year: 2026, month: 10, day: 16 })).toBe("2026/2027");
    expect(computeJubaMonthlyFilingDeadline(2026, 9, 15).dueDateIso).toBe(
      "2026-10-15T23:59:59+02:00",
    );

    const hours = extractOfficerHours({
      handoff: {
        officer_hours: {
          on_duty: false,
          hours: "08:00–17:00 CAT",
          next_on_duty: "2026-10-19T06:00:00Z",
        },
      },
    });
    expect(hours?.onDuty).toBe(false);
    expect(formatNextShiftJuba("invalid-date", "en")).toBeNull();
    expect(formatNextShiftJuba("2026-10-19T06:00:00Z", "en")).toContain("08:00");

    expect(resolveMenuKeyNavigation("ArrowDown", 2, 3)).toEqual({
      nextIndex: 0,
      closeAndRestoreFocus: false,
      handled: true,
    });
    expect(resolveMenuKeyNavigation("Escape", 1, 3)).toEqual({
      nextIndex: 1,
      closeAndRestoreFocus: true,
      handled: true,
    });
    expect(shouldEnableLowDataMode({ effectiveType: "2g" })).toBe(true);
    expect(shouldEnableLowDataMode({ saveData: true })).toBe(true);
    expect(shouldEnableLowDataMode({ downlink: 0.3 })).toBe(true);
    expect(shouldEnableLowDataMode({ effectiveType: "4g", downlink: 10 })).toBe(false);
    expect(shouldEnableLowDataMode({ effectiveType: "4g" }, true)).toBe(true);

    const arDark = resolveSurfaceDesignContext({
      locale: "ar",
      mode: "dark",
      lowDataMode: true,
    });
    expect(arDark.dir).toBe("rtl");
    expect(arDark.theme.mode).toBe("dark");
    expect(arDark.lineHeight).toBe(1.68);
    expect(arDark.fontVariantNumeric).toBe("tabular-nums");
    expect(arDark.transitionDurationMs).toBe(0);
    expect(arDark.suppressDecorativeIcons).toBe(true);

    const enLight = resolveSurfaceDesignContext({ locale: "en", mode: "light" });
    expect(enLight.dir).toBe("ltr");
    expect(enLight.theme.mode).toBe("light");
    expect(enLight.transitionDurationMs).toBe(120);
  });
});
