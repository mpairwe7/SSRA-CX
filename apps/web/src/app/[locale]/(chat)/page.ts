/**
 * Chat route group (`apps/web/src/app/[locale]/(chat)/page.ts`)
 */

import { resolveGenerativeUIComponent } from "@ssra/chat-ui";
import type { Answer } from "@ssra/contracts";

export function presentTurnAnswerForWeb(answer: Answer, lowDataMode = false) {
  const fullText = answer.segments.map((s) => s.text).join(" ");
  const ui = resolveGenerativeUIComponent(answer.ui_component, fullText, { lowDataMode });
  return {
    text: fullText,
    citations: answer.citations,
    isEstimate: answer.is_estimate,
    abstained: answer.abstained,
    ui,
  };
}
