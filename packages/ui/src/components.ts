/**
 * WCAG 2.2 AA & RTL-Aware Accessible UI Primitives (`packages/ui/src/components.ts` — Section 9.3).
 */

import type { LocaleCode } from "@ssra/contracts";
import { getMessages } from "@ssra/i18n";
import { getHtmlLayoutProps, SSRA_DESIGN_TOKENS } from "./index.js";

export interface AccessibleBannerDescriptor {
  readonly role: "region";
  readonly ariaLabel: string;
  readonly lang: LocaleCode;
  readonly dir: "ltr" | "rtl";
  readonly minTouchTargetPx: number;
  readonly cashFreeNotice: string;
  readonly assistantDisclosure: string;
  readonly officialPortalUrl: "https://etax.nra.gov.ss/";
}

export function buildOfficialHeaderBanner(locale: LocaleCode): AccessibleBannerDescriptor {
  const layout = getHtmlLayoutProps(locale);
  const messages = getMessages(locale);
  return {
    role: "region",
    ariaLabel: messages.appTitle,
    lang: layout.lang,
    dir: layout.dir,
    minTouchTargetPx: SSRA_DESIGN_TOKENS.minTouchTargetPx,
    cashFreeNotice: messages.cashFreeBanner,
    assistantDisclosure: messages.assistantDisclosure,
    officialPortalUrl: "https://etax.nra.gov.ss/",
  };
}
