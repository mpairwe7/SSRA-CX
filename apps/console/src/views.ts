/**
 * Phase 3 Staff Console Interactive View Models (`apps/console/src/views.ts` — Section 3, 7, 9.2).
 */

import { authorizeConsoleAccess, type ConsoleSession, KNOWLEDGE_RELEASE_STEPS } from "./proxy.js";

export interface CopilotDraftReviewAction {
  readonly conversationId: string;
  readonly staffId: string;
  readonly decision: "APPROVE_AND_SEND" | "EDIT_AND_SEND" | "REJECT_AND_WRITE_MANUAL";
  readonly citationsIncluded: readonly string[];
}

export function validateCopilotDraftApproval(
  session: ConsoleSession | null,
  action: CopilotDraftReviewAction,
): { readonly valid: boolean; readonly error?: string } {
  const auth = authorizeConsoleAccess(session);
  if (!auth.allowed) {
    return { valid: false, error: auth.reason ?? "UNAUTHORIZED" };
  }
  if (action.decision === "APPROVE_AND_SEND" && action.citationsIncluded.length === 0) {
    return {
      valid: false,
      error: "PRINCIPLE_1_GROUNDED_OR_SILENT_CITATIONS_REQUIRED",
    };
  }
  return { valid: true };
}

export function buildKnowledgeReleasePipelineView(currentStepIndex: number) {
  return KNOWLEDGE_RELEASE_STEPS.map((step, idx) => ({
    step,
    state:
      idx < currentStepIndex
        ? ("COMPLETED" as const)
        : idx === currentStepIndex
          ? ("ACTIVE" as const)
          : ("PENDING" as const),
  }));
}
