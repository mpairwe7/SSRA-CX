/**
 * Taxpayer Web PWA UI Components & Streaming Turn Metadata Continuity (`apps/web/src/components/index.ts` — Section 9.3, 16).
 */

import { renderGenerativeUICard } from "@ssra/chat-ui";
import type { Answer, Citation, LocaleCode } from "@ssra/contracts";
import { buildOfficialHeaderBanner, extractOfficerHours, type OfficerDutyHours } from "@ssra/ui";

export interface TaxpayerTurnState {
  readonly serverTurnId: string | null;
  readonly citations: readonly Citation[];
  readonly nextActions: readonly string[];
  readonly officerHours?: OfficerDutyHours | undefined;
  readonly escalationRequired: boolean;
}

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

/**
 * Single authoritative place applying SSE `metadata`/`done` frame fields to a turn
 * so `next_actions`, `citations`, and `officer_hours` never drift or get dropped.
 */
export function applyTaxpayerTurnMeta(
  turn: TaxpayerTurnState,
  meta: Record<string, unknown>,
): TaxpayerTurnState {
  const nextActions = Array.isArray(meta.next_actions)
    ? meta.next_actions.filter((a): a is string => typeof a === "string")
    : turn.nextActions;
  const citations = Array.isArray(meta.citations) ? (meta.citations as Citation[]) : turn.citations;
  return {
    serverTurnId: typeof meta.turn_id === "string" ? meta.turn_id : turn.serverTurnId,
    citations,
    nextActions,
    officerHours: extractOfficerHours(meta) ?? turn.officerHours,
    escalationRequired:
      typeof meta.escalation_required === "boolean"
        ? meta.escalation_required
        : turn.escalationRequired,
  };
}
