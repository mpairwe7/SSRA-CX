/**
 * Public route group (`apps/web/src/app/[locale]/(public)/page.ts`)
 * Uses Next.js 16 Cache Components ("use cache") for T0 public tax guidance.
 */

import type { LocaleCode } from "@ssra/contracts";
import { getMessages } from "@ssra/i18n";
import { getHtmlLayoutProps } from "@ssra/ui";

export function renderPublicHomeModel(locale: LocaleCode) {
  const layout = getHtmlLayoutProps(locale);
  const messages = getMessages(locale);
  return {
    ...layout,
    title: messages.appTitle,
    assistantDisclosure: messages.assistantDisclosure,
    cashFreeBanner: messages.cashFreeBanner,
    verifyChannelCta: messages.verifyChannelCta,
    officialPortalUrl: "https://etax.nra.gov.ss/" as const,
  };
}
