import type { LocaleCode } from "@ssra/contracts";
import { getTextDirection } from "@ssra/i18n";

export type ColorMode = "light" | "dark";

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
    blue: "#134074",
    gold: "#c99700",
    green: "#1b7f4c",
    red: "#b42318",
    surface: "#f8fafc",
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
      focusRingColor: "#c99700",
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
  },
  motion: {
    fastDurationMs: 120,
    standardDurationMs: 180,
    easingCss: "cubic-bezier(0.2, 0, 0, 1)",
  },
  minTouchTargetPx: 44, // WCAG 2.2 AA SC 2.5.8 / AAA SC 2.5.5 target size
  focusOutlineCss: "2px solid #c99700", // WCAG 2.2 SC 2.4.11 / SC 2.4.13 focus appearance (>= 3:1)
  focusOutlineOffsetPx: 2,
} as const;

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
}): ResolvedSurfaceDesignContext {
  const dir = getTextDirection(options.locale);
  const mode = options.mode ?? "light";
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
