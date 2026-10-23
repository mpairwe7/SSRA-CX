import { describe, expect, it } from "vitest";
import {
  buildAccessibleOtpInputProps,
  buildThemeCssVariables,
  computeJubaMonthlyFilingDeadline,
  computeWcagContrastRatio,
  extractOfficerHours,
  formatNextShiftJuba,
  getHtmlLayoutProps,
  getSouthSudanFiscalYear,
  isJwtTokenExpired,
  looksLikeJwtFormat,
  resolveMenuKeyNavigation,
  resolveResponsiveViewportContext,
  resolveSurfaceDesignContext,
  SSRA_DESIGN_TOKENS,
  sanitizeBearerOrSubjectToken,
  shouldEnableLowDataMode,
  verifyThemeColorCoherency,
} from "../src/index.js";

describe("@ssra/ui design tokens and RTL layout", () => {
  it("enforces WCAG 2.2 AA touch target minimum, SC 3.3.8 OTP autofill, and Arabic RTL direction", () => {
    expect(SSRA_DESIGN_TOKENS.minTouchTargetPx).toBeGreaterThanOrEqual(44);
    expect(SSRA_DESIGN_TOKENS.focusOutlineCss).toContain("2px solid");
    expect(SSRA_DESIGN_TOKENS.typography.fontFamilyOpsSans).toContain("IBM Plex Sans");
    expect(SSRA_DESIGN_TOKENS.typography.fontFamilyOpsMono).toContain("IBM Plex Mono");
    expect(SSRA_DESIGN_TOKENS.typography.fontFeatureSettings).toBe('"cv11", "ss01"');
    expect(SSRA_DESIGN_TOKENS.typography.opsTypeScalePx["2xl"]).toBe(34);
    expect(SSRA_DESIGN_TOKENS.chatv2.railWidthPx).toBe(300);
    expect(SSRA_DESIGN_TOKENS.opsConsole.collapsedRailWidthPx).toBe(52);
    expect(SSRA_DESIGN_TOKENS.opsConsole.expandedRailWidthPx).toBe(208);
    expect(SSRA_DESIGN_TOKENS.opsConsole.seriesPaletteDark).toHaveLength(8);
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

    // High-contrast mode & WCAG 2.2 AA/AAA contrast coherency across all 3 themes
    const hcCtx = resolveSurfaceDesignContext({ locale: "en", prefersHighContrast: true });
    expect(hcCtx.theme.mode).toBe("high-contrast");
    for (const mode of ["light", "dark", "high-contrast"] as const) {
      const report = verifyThemeColorCoherency(SSRA_DESIGN_TOKENS.themes[mode]);
      expect(report.passesWcagAA).toBe(true);
      expect(report.passesWcagAAA).toBe(true);
      const cssVars = buildThemeCssVariables(SSRA_DESIGN_TOKENS.themes[mode]);
      expect(cssVars["--ssra-font-numeric"]).toBe("tabular-nums");
    }
    expect(computeWcagContrastRatio("#ffffff", "#000000")).toBe(21);

    // Mobile responsiveness: 320px WCAG Reflow floor, 100dvh/100svh, safe-area insets & coarse pointer targets
    const mobile320 = resolveResponsiveViewportContext({
      viewportWidthPx: 320,
      pointer: "coarse",
      virtualKeyboardOpen: true,
    });
    expect(mobile320.breakpoint).toBe("xs_320");
    expect(mobile320.reflowSafeAt320Px).toBe(true);
    expect(mobile320.viewportHeightCss).toBe("100svh");
    expect(mobile320.effectiveTouchTargetPx).toBe(48);
    expect(mobile320.navigationPattern).toBe("bottom_sheet_rail");

    const desktop1280 = resolveResponsiveViewportContext({
      viewportWidthPx: 1280,
      pointer: "fine",
    });
    expect(desktop1280.breakpoint).toBe("lg_desktop");
    expect(desktop1280.viewportHeightCss).toBe("100dvh");
    expect(desktop1280.effectiveTouchTargetPx).toBe(44);
    expect(desktop1280.navigationPattern).toBe("collapsible_side_rail");

    // SEC2-G7: Zero-width/BOM token sanitizer & proactive clock-skew JWT expiry check
    expect(sanitizeBearerOrSubjectToken("  \u200bsub_taxpayer_amina_01\uFEFF… ")).toBe(
      "sub_taxpayer_amina_01",
    );
    const expPayload = btoa(JSON.stringify({ exp: 1_700_000_000 })).replace(/=+$/, "");
    const sampleJwt = `eyJhbGciOiJFUzI1NiJ9.${expPayload}.sig_part`;
    expect(looksLikeJwtFormat(sampleJwt)).toBe(true);
    expect(looksLikeJwtFormat("not-a-jwt")).toBe(false);
    expect(isJwtTokenExpired(sampleJwt, 10, 1_700_000_000 * 1000 - 5_000)).toBe(true);
    expect(isJwtTokenExpired(sampleJwt, 10, 1_700_000_000 * 1000 - 30_000)).toBe(false);
  });
});
