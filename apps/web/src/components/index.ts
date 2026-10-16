/**
 * Taxpayer Web PWA UI Components (`apps/web/src/components/index.ts` — Section 9.3, 16).
 */

import { renderGenerativeUICard } from "@ssra/chat-ui";
import type { Answer, LocaleCode } from "@ssra/contracts";
import { buildOfficialHeaderBanner } from "@ssra/ui";

export function buildTaxpayerChatTurnView(answer: Answer, locale: LocaleCode, lowDataMode = false) {
  const header = buildOfficialHeaderBanner(locale);
  const fullText = answer.segments.map((s) => s.text).join(" ");
  const card = renderGenerativeUICard(answer.ui_component, fullText, {
    locale,
    lowDataMode,
  });
  return {
    header,
    card,
    citations: answer.citations,
    isEstimate: answer.is_estimate,
    abstained: answer.abstained,
  };
}
