import type { LocaleCode } from "@ssra/contracts";
import { getTextDirection } from "@ssra/i18n";

export type ColorMode = "light" | "dark" | "high-contrast";

export interface SemanticThemeTokens {
  readonly mode: ColorMode;
  readonly bgCanvas: string;
  readonly bgSurface: string;
  readonly bgElevated: string;
  readonly bgSubtle: string;
  readonly textPrimary: string;
  readonly textSecondary: string;
  readonly textMuted: string;
  readonly borderSubtle: string;
  readonly borderStrong: string;
  readonly interactivePrimary: string;
  readonly interactivePrimaryHover: string;
  readonly interactivePrimaryText: string;
  readonly statusSuccessText: string;
  readonly statusSuccessBg: string;
  readonly statusWarningText: string;
  readonly statusWarningBg: string;
  readonly statusErrorText: string;
  readonly statusErrorBg: string;
  readonly focusRingColor: string;
}

export const SSRA_DESIGN_TOKENS = {
  colors: {
    navy: "#0b2545",
    blue: "#0f47af", // White Nile Azure (Republic of South Sudan flag chevron)
    gold: "#c99700", // Guiding Star & Savanna Acacia Gold
    green: "#078930", // Equatoria Forest & Agriculture Green
    red: "#b42318", // Sovereign Crimson
    surface: "#f6f7f2", // Warm Savanna Cotton Paper
    nileDusk: "#091310", // Natural Nile & Canopy Dusk
  },
  oklchPalette: {
    brandNavy: "oklch(0.26 0.07 252)",
    brandBlue: "oklch(0.42 0.16 258)",
    brandGold: "oklch(0.72 0.15 84)",
    civicGreen: "oklch(0.54 0.16 148)",
    alertRed: "oklch(0.48 0.18 28)",
    surfaceWarmLight: "oklch(0.978 0.008 115)",
    surfaceDeepDark: "oklch(0.17 0.025 162)",
  },
  themes: {
    light: {
      mode: "light",
      bgCanvas: "#f8fafc",
      bgSurface: "#ffffff",
      bgElevated: "#f1f5f9",
      bgSubtle: "#eef2f6",
      textPrimary: "#0f172a", // 17.4:1 on #ffffff (WCAG AAA)
      textSecondary: "#334155", // 9.8:1 on #ffffff (WCAG AAA)
      textMuted: "#475569", // 7.2:1 on #ffffff (WCAG AAA)
      borderSubtle: "#cbd5e1",
      borderStrong: "#64748b", // 4.6:1 (WCAG SC 1.4.11 non-text contrast)
      interactivePrimary: "#0b2545", // 15.1:1 on #ffffff (WCAG AAA)
      interactivePrimaryHover: "#134074",
      interactivePrimaryText: "#ffffff",
      statusSuccessText: "#146c43", // 6.5:1 on #eaf6f0
      statusSuccessBg: "#eaf6f0",
      statusWarningText: "#7c4a03", // 7.1:1 on #fef7e6
      statusWarningBg: "#fef7e6",
      statusErrorText: "#b42318", // 6.1:1 on #fef3f2
      statusErrorBg: "#fef3f2",
      focusRingColor: "#8a6500", // >= 4.7:1 on #ffffff (WCAG 2.2 SC 2.4.13)
    },
    dark: {
      mode: "dark",
      bgCanvas: "#081221",
      bgSurface: "#0f1e33",
      bgElevated: "#162a45",
      bgSubtle: "#1d3557",
      textPrimary: "#f8fafc", // 16.2:1 on #0f1e33 (WCAG AAA)
      textSecondary: "#cbd5e1", // 11.4:1 on #0f1e33 (WCAG AAA)
      textMuted: "#94a3b8", // 6.3:1 on #0f1e33 (WCAG AA+)
      borderSubtle: "#294366",
      borderStrong: "#64748b",
      interactivePrimary: "#e2b93b", // 9.7:1 against #081221
      interactivePrimaryHover: "#f0c954",
      interactivePrimaryText: "#081221",
      statusSuccessText: "#6ee7b7",
      statusSuccessBg: "#0b2e23",
      statusWarningText: "#fcd34d",
      statusWarningBg: "#332407",
      statusErrorText: "#fca5a5",
      statusErrorBg: "#3b1219",
      focusRingColor: "#f0c954",
    },
    "high-contrast": {
      mode: "high-contrast",
      bgCanvas: "#000000",
      bgSurface: "#050b14",
      bgElevated: "#0b192c",
      bgSubtle: "#10233d",
      textPrimary: "#ffffff", // 20.1:1 on #050b14 (WCAG AAA+)
      textSecondary: "#f8fafc", // 19.3:1 on #050b14 (WCAG AAA+)
      textMuted: "#e2e8f0", // 16.1:1 on #050b14 (WCAG AAA+)
      borderSubtle: "#94a3b8",
      borderStrong: "#ffffff", // 20.1:1 (forced-colors & sunlight glare safe)
      interactivePrimary: "#ffd60a", // 14.3:1 against #050b14
      interactivePrimaryHover: "#ffe14c",
      interactivePrimaryText: "#000000",
      statusSuccessText: "#86efac",
      statusSuccessBg: "#052e16",
      statusWarningText: "#fde047",
      statusWarningBg: "#291d02",
      statusErrorText: "#fecaca",
      statusErrorBg: "#310b11",
      focusRingColor: "#ffd60a",
    },
  } satisfies Record<ColorMode, SemanticThemeTokens>,
  typography: {
    fontFamilyLatin:
      'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif',
    fontFamilyArabic: '"Noto Sans Arabic", "Geeza Pro", "Segoe UI", Tahoma, system-ui, sans-serif',
    fontFamilyMono:
      'ui-monospace, "Cascadia Mono", "Segoe UI Mono", "Liberation Mono", Menlo, monospace',
    numericFeatureSettings: "tabular-nums",
    lineHeightLtr: 1.5,
    lineHeightRtl: 1.68,
    fluidBodyClampCss: "clamp(1rem, 0.96rem + 0.2vw, 1.125rem)",
    fluidHeadingClampCss: "clamp(1.25rem, 1.1rem + 0.75vw, 1.75rem)",
    maxMeasureCh: 65,
  },
  motion: {
    fastDurationMs: 120,
    standardDurationMs: 180,
    easingCss: "cubic-bezier(0.2, 0, 0, 1)",
  },
  minTouchTargetPx: 44, // WCAG 2.2 AA SC 2.5.8 / AAA SC 2.5.5 target size
  coarsePointerTouchTargetPx: 48, // Enhanced tap comfort on mobile touchscreens
  minTargetSpacingPx: 8, // WCAG 2.2 SC 2.5.8 target spacing
  focusOutlineCss: "2px solid #c99700", // WCAG 2.2 SC 2.4.11 / SC 2.4.13 focus appearance (>= 3:1)
  focusOutlineOffsetPx: 2,
} as const;

function parseHexChannel(hex: string, offset: number): number {
  const val = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
  return val <= 0.03928 ? val / 12.92 : ((val + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hexColor: string): number {
  const clean = hexColor.trim().replace(/^#/, "");
  if (clean.length !== 6) {
    throw new RangeError(`Expected 6-digit hex color, got '${hexColor}'`);
  }
  const r = parseHexChannel(clean, 0);
  const g = parseHexChannel(clean, 2);
  const b = parseHexChannel(clean, 4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Compute exact WCAG 2.2 relative luminance contrast ratio (`1.0`..`21.0`) between two `#RRGGBB` colors.
 */
export function computeWcagContrastRatio(foregroundHex: string, backgroundHex: string): number {
  const l1 = relativeLuminance(foregroundHex);
  const l2 = relativeLuminance(backgroundHex);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return Number(((lighter + 0.05) / (darker + 0.05)).toFixed(2));
}

export interface ThemeContrastAuditReport {
  readonly mode: ColorMode;
  readonly textPrimaryContrast: number;
  readonly textSecondaryContrast: number;
  readonly textMutedContrast: number;
  readonly interactiveContrast: number;
  readonly statusSuccessContrast: number;
  readonly statusWarningContrast: number;
  readonly statusErrorContrast: number;
  readonly passesWcagAA: boolean;
  readonly passesWcagAAA: boolean;
}

/**
 * Audit a semantic theme token set for WCAG 2.2 AA (>= 4.5:1) and AAA (>= 7.0:1) contrast coherency.
 */
export function verifyThemeColorCoherency(theme: SemanticThemeTokens): ThemeContrastAuditReport {
  const textPrimaryContrast = computeWcagContrastRatio(theme.textPrimary, theme.bgSurface);
  const textSecondaryContrast = computeWcagContrastRatio(theme.textSecondary, theme.bgSurface);
  const textMutedContrast = computeWcagContrastRatio(theme.textMuted, theme.bgSurface);
  const interactiveContrast = computeWcagContrastRatio(
    theme.interactivePrimaryText,
    theme.interactivePrimary,
  );
  const statusSuccessContrast = computeWcagContrastRatio(
    theme.statusSuccessText,
    theme.statusSuccessBg,
  );
  const statusWarningContrast = computeWcagContrastRatio(
    theme.statusWarningText,
    theme.statusWarningBg,
  );
  const statusErrorContrast = computeWcagContrastRatio(theme.statusErrorText, theme.statusErrorBg);

  const passesWcagAA =
    textPrimaryContrast >= 4.5 &&
    textSecondaryContrast >= 4.5 &&
    textMutedContrast >= 4.5 &&
    interactiveContrast >= 4.5 &&
    statusSuccessContrast >= 4.5 &&
    statusWarningContrast >= 4.5 &&
    statusErrorContrast >= 4.5;

  const passesWcagAAA =
    textPrimaryContrast >= 7.0 && textSecondaryContrast >= 7.0 && interactiveContrast >= 7.0;

  return {
    mode: theme.mode,
    textPrimaryContrast,
    textSecondaryContrast,
    textMutedContrast,
    interactiveContrast,
    statusSuccessContrast,
    statusWarningContrast,
    statusErrorContrast,
    passesWcagAA,
    passesWcagAAA,
  };
}

/**
 * Generate CSS custom properties (`--ssra-*`) for a semantic theme with `color-scheme` and `tabular-nums`.
 */
export function buildThemeCssVariables(theme: SemanticThemeTokens): Record<string, string> {
  return {
    "color-scheme": theme.mode === "light" ? "light" : "dark",
    "--ssra-bg-canvas": theme.bgCanvas,
    "--ssra-bg-surface": theme.bgSurface,
    "--ssra-bg-elevated": theme.bgElevated,
    "--ssra-bg-subtle": theme.bgSubtle,
    "--ssra-text-primary": theme.textPrimary,
    "--ssra-text-secondary": theme.textSecondary,
    "--ssra-text-muted": theme.textMuted,
    "--ssra-border-subtle": theme.borderSubtle,
    "--ssra-border-strong": theme.borderStrong,
    "--ssra-interactive-primary": theme.interactivePrimary,
    "--ssra-interactive-primary-hover": theme.interactivePrimaryHover,
    "--ssra-interactive-primary-text": theme.interactivePrimaryText,
    "--ssra-focus-ring": theme.focusRingColor,
    "--ssra-font-numeric": SSRA_DESIGN_TOKENS.typography.numericFeatureSettings,
  };
}

export function getHtmlLayoutProps(locale: LocaleCode): {
  readonly lang: LocaleCode;
  readonly dir: "ltr" | "rtl";
} {
  return {
    lang: locale,
    dir: getTextDirection(locale),
  };
}

export interface ResolvedSurfaceDesignContext {
  readonly lang: LocaleCode;
  readonly dir: "ltr" | "rtl";
  readonly theme: SemanticThemeTokens;
  readonly fontFamily: string;
  readonly lineHeight: number;
  readonly fontVariantNumeric: "tabular-nums";
  readonly transitionDurationMs: number;
  readonly suppressDecorativeIcons: boolean;
}

/**
 * Resolve semantic color tokens, script-aware typography, RTL line height, and restrained motion
 * for Light/Dark modes and 2G Low-Data / Reduced-Motion contexts.
 */
export function resolveSurfaceDesignContext(options: {
  readonly locale: LocaleCode;
  readonly mode?: ColorMode;
  readonly lowDataMode?: boolean;
  readonly prefersReducedMotion?: boolean;
  readonly prefersHighContrast?: boolean;
}): ResolvedSurfaceDesignContext {
  const dir = getTextDirection(options.locale);
  const mode: ColorMode = options.prefersHighContrast ? "high-contrast" : (options.mode ?? "light");
  const zeroMotion = options.lowDataMode === true || options.prefersReducedMotion === true;
  return {
    lang: options.locale,
    dir,
    theme: SSRA_DESIGN_TOKENS.themes[mode],
    fontFamily:
      dir === "rtl"
        ? SSRA_DESIGN_TOKENS.typography.fontFamilyArabic
        : SSRA_DESIGN_TOKENS.typography.fontFamilyLatin,
    lineHeight:
      dir === "rtl"
        ? SSRA_DESIGN_TOKENS.typography.lineHeightRtl
        : SSRA_DESIGN_TOKENS.typography.lineHeightLtr,
    fontVariantNumeric: SSRA_DESIGN_TOKENS.typography.numericFeatureSettings,
    transitionDurationMs: zeroMotion ? 0 : SSRA_DESIGN_TOKENS.motion.fastDurationMs,
    suppressDecorativeIcons: options.lowDataMode === true,
  };
}

export * from "./components.js";
export * from "./juba-calendar.js";
