/**
 * Staff Console Visual Document Inspection Viewer, Officer Call Brief Card & Wrap-Up Panel
 * (`apps/console/src/document-inspection.ts`).
 *
 * Ported from:
 * - `FinalYearProject/App/frontend/src/components/staff/DocumentInspectionViewer.tsx`
 * - `FinalYearProject/App/frontend/src/components/staff/calls/CallBriefCard.tsx`
 * - `FinalYearProject/App/frontend/src/components/staff/calls/WrapUpPanel.tsx`
 */

export interface BoundingBox {
  readonly x1: number;
  readonly y1: number;
  readonly x2: number;
  readonly y2: number;
}

export interface ExtractedDocumentField {
  readonly id: string;
  readonly name: string;
  readonly value: string;
  readonly confidence: number;
  readonly source: "vector_glyph" | "ocr_inset" | "ruling_grid" | "vlm" | "manual";
  readonly status: "auto_use" | "use_with_warning" | "review_required";
  readonly page: number;
  readonly bbox?: BoundingBox | undefined;
}

/**
 * Build the visual state for the Staff Document Inspection Viewer (`DocumentInspectionViewer.tsx`),
 * including page clamping, zoom scaling, and whether all `review_required` fields have been resolved.
 */
export function buildStaffDocumentInspectionViewerState(params: {
  readonly documentName: string;
  readonly pageCount: number;
  readonly currentPage: number;
  readonly zoomLevel: number;
  readonly fields: readonly ExtractedDocumentField[];
}) {
  const safePageCount = Math.max(1, params.pageCount);
  const clampedPage = Math.max(1, Math.min(safePageCount, params.currentPage));
  const clampedZoom = Math.max(50, Math.min(200, params.zoomLevel));
  const pageFields = params.fields.filter((f) => f.page === clampedPage);
  const reviewRequiredCount = params.fields.filter((f) => f.status === "review_required").length;
  const autoUseCount = params.fields.filter((f) => f.status === "auto_use").length;

  return {
    documentName: params.documentName,
    pageBadge: `Page ${clampedPage} of ${safePageCount}`,
    currentPage: clampedPage,
    canPreviousPage: clampedPage > 1,
    canNextPage: clampedPage < safePageCount,
    zoomLevel: clampedZoom,
    canvasScaleTransform: `scale(${clampedZoom / 100})`,
    pageFields,
    reviewRequiredCount,
    autoUseCount,
    canCompleteDocumentReview: reviewRequiredCount === 0,
  };
}

/**
 * Resolve an officer's HITL decision (`confirm_extracted` or `override_value`) on a flagged OCR field.
 */
export function resolveExtractedFieldReview(
  field: ExtractedDocumentField,
  decision: "confirm_extracted" | "override_value",
  correctedValue?: string,
): ExtractedDocumentField {
  const nextVal =
    decision === "override_value" && correctedValue && correctedValue.trim().length > 0
      ? correctedValue.trim()
      : field.value;
  return {
    ...field,
    value: nextVal,
    source: decision === "override_value" ? "manual" : field.source,
    status: "auto_use",
    confidence: 1.0,
  };
}

export interface BriefClaimItem {
  readonly text: string;
  readonly turn_seqs: readonly number[];
}

export interface OfficerCallBriefModel {
  readonly why_officer?: BriefClaimItem | undefined;
  readonly caller_goal: BriefClaimItem;
  readonly ai_already_said: readonly BriefClaimItem[];
  readonly still_open: readonly BriefClaimItem[];
  readonly details_given: readonly {
    readonly label: string;
    readonly value: string;
    readonly turn_seqs: readonly number[];
  }[];
  readonly sentiment: "calm" | "confused" | "frustrated" | "distressed";
  readonly suggested_opener: string;
  readonly turns_covered: number;
  /** The model that wrote the brief; null when it was built by keyword rules. */
  readonly model: string | null;
  readonly fallback?: boolean | undefined;
}

export const RULE_BASED_BRIEF_ATTRIBUTION = "Built by keyword rules, not by a model";

export const MOOD_LABEL: Record<OfficerCallBriefModel["sentiment"], string> = {
  calm: "Calm",
  confused: "Confused",
  frustrated: "Frustrated",
  distressed: "Distressed",
};

export function buildCallBriefCardView(params: {
  readonly brief: OfficerCallBriefModel | null;
  readonly loading: boolean;
  readonly compact?: boolean | undefined;
  readonly expanded?: boolean | undefined;
}) {
  if (!params.brief) {
    return {
      mode: "pending" as const,
      statusText: params.loading
        ? "Writing the brief…"
        : "No brief yet — the caller has not said enough.",
      moodLabel: null,
      modelAttribution: null,
    };
  }
  if (params.compact && !params.expanded) {
    return {
      mode: "compact" as const,
      statusText: params.brief.caller_goal.text,
      moodLabel: MOOD_LABEL[params.brief.sentiment],
      modelAttribution: params.brief.model ?? RULE_BASED_BRIEF_ATTRIBUTION,
    };
  }
  return {
    mode: "full" as const,
    statusText: params.brief.caller_goal.text,
    moodLabel: MOOD_LABEL[params.brief.sentiment],
    modelAttribution: params.brief.fallback
      ? "no model answered — check the transcript"
      : (params.brief.model ?? RULE_BASED_BRIEF_ATTRIBUTION),
  };
}

export function validateWrapUpFormSubmission(params: {
  readonly note: string;
  readonly outcome: "resolved" | "escalated" | "callback_scheduled";
  readonly satisfaction: number | null;
  readonly notSaid: boolean;
  readonly aiRating?: number | null | undefined;
}): {
  readonly valid: boolean;
  readonly error: string | null;
  readonly payload?: {
    readonly note: string;
    readonly outcome: "resolved" | "escalated" | "callback_scheduled";
    readonly caller_satisfaction_status: "answered" | "not_said";
    readonly caller_satisfaction?: number | undefined;
    readonly rating?: number | undefined;
  };
} {
  if (!params.note.trim()) {
    return { valid: false, error: "Please provide a call wrap-up note" };
  }
  if (params.satisfaction == null && !params.notSaid) {
    return {
      valid: false,
      error: "Record how satisfied the caller said they were, or mark that they didn't say",
    };
  }
  if (
    !params.notSaid &&
    (params.satisfaction == null || params.satisfaction < 1 || params.satisfaction > 5)
  ) {
    return { valid: false, error: "Caller satisfaction must be between 1 and 5" };
  }
  return {
    valid: true,
    error: null,
    payload: {
      note: params.note.trim(),
      outcome: params.outcome,
      caller_satisfaction_status: params.notSaid ? "not_said" : "answered",
      ...(params.notSaid ? {} : { caller_satisfaction: params.satisfaction ?? undefined }),
      ...(params.aiRating != null ? { rating: params.aiRating } : {}),
    },
  };
}
