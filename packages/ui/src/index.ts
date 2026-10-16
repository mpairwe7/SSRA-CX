import type { LocaleCode } from "@ssra/contracts";
import { getTextDirection } from "@ssra/i18n";

export const SSRA_DESIGN_TOKENS = {
  colors: {
    navy: "#0b2545",
    blue: "#134074",
    gold: "#c99700",
    green: "#1b7f4c",
    red: "#b42318",
    surface: "#f8fafc",
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

export * from "./components.js";
export * from "./juba-calendar.js";
