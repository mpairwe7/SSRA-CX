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
  minTouchTargetPx: 44, // WCAG 2.2 AA target size
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
