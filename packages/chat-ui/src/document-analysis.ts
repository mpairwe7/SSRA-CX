/**
 * Taxpayer Document & Screenshot Inspection Modal & Attachment Helpers (`packages/chat-ui/src/document-analysis.ts`).
 *
 * Ported from `FinalYearProject/App/frontend/src/lib/attachments.ts` &
 * `src/components/DocumentInspectionModal.tsx`, adapted for South Sudan Revenue Authority (SSRA / NRA):
 * - `stripStepPrefix`: prevents duplicate numbering ("1. Step 1: Click…") in `<ol>` lists.
 * - `formatDocType`: multilingual labels across `en`, `ar`, and `pga`.
 * - `buildDocumentInspectionModalView`: builds contextual quick prompts, portal screenshot
 *   hotspots (`is-error`, `is-action`, `is-target`), and SSP tax reconciliation cards.
 */

import type { LocaleCode } from "@ssra/contracts";

export const MAX_ATTACHMENTS_PER_TURN = 3;
export const MAX_ATTACHMENT_BYTES = 40 * 1024 * 1024;
export const ATTACHMENT_ACCEPT = ".pdf,.docx,.xlsx,.csv,.txt,image/*";
export const THUMBNAIL_EDGE_PX = 56;

const SAFE_DATA_IMAGE_RE = /^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/;

/**
 * Enforce CSP `img-src 'self' data:` safety: attachment chip thumbnails must use
 * `data:image/{jpeg,png,webp};base64,...` — never `blob:` URLs (which break under strict CSP).
 */
export function isCspSafeImagePreviewDataUrl(candidate: string | undefined | null): boolean {
  if (!candidate) return false;
  return SAFE_DATA_IMAGE_RE.test(candidate);
}

export interface DocumentTaxReconciliation {
  readonly status:
    | "verified"
    | "discrepancy_detected"
    | "unreconciled_partial"
    | "informational_only";
  readonly subtotal_ssp?: number | null | undefined;
  readonly tax_ssp?: number | null | undefined;
  readonly total_ssp?: number | null | undefined;
  readonly effective_rate?: number | null | undefined;
  readonly variance_ssp?: number | null | undefined;
  readonly notes?: readonly string[] | undefined;
}

export interface ScreenshotHotspot {
  readonly id: string;
  readonly type: "error" | "action" | "target";
  readonly label: string;
  readonly instruction: string;
  readonly bbox?: readonly [number, number, number, number] | undefined;
  readonly dom_selector?: string | undefined;
}

export interface ScreenshotGuidance {
  readonly is_screenshot?: boolean | undefined;
  readonly detected_portal?: string | undefined;
  readonly portal_url?: string | undefined;
  readonly portal_category?: string | undefined;
  readonly detected_state?: string | undefined;
  readonly issues_detected?: readonly string[] | undefined;
  readonly steps?: readonly string[] | undefined;
  readonly hotspots?: readonly ScreenshotHotspot[] | undefined;
  readonly direct_action?: { readonly label: string; readonly url: string } | undefined;
}

export interface DocumentAnalysisData {
  readonly documentId: string;
  readonly filename: string;
  readonly kind: string;
  readonly sizeBytes: number;
  readonly docType: string;
  readonly confidence: number;
  readonly fields?:
    | {
        readonly tins?: readonly string[] | undefined;
        readonly amounts?: readonly string[] | undefined;
        readonly references?: readonly string[] | undefined;
      }
    | undefined;
  readonly summary?: string | undefined;
  readonly taxReconciliation?: DocumentTaxReconciliation | undefined;
  readonly screenshot_guidance?: ScreenshotGuidance | undefined;
  readonly warnings?: readonly string[] | undefined;
}

export function stripStepPrefix(step: string): string {
  return step.replace(/^\s*step\s*\d+\s*[:.)\-–]\s*/i, "");
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${Math.round(bytes)} B`;
}

const DOC_TYPE_LABELS_EN: Record<string, string> = {
  receipt: "Payment Receipt",
  tin_card: "TIN Certificate",
  national_id: "National ID / Passport",
  assessment: "Tax Assessment Notice",
  customs_declaration: "TANCIS++ Customs Declaration",
  filing_form: "Tax Return Form",
  invoice: "Sales Tax Invoice",
  statutory_act: "South Sudan Tax Law / Act",
  portal_screenshot: "SSRA e-Tax Portal Screenshot",
  generic: "Document",
};

const DOC_TYPE_LABELS_AR: Record<string, string> = {
  receipt: "إيصال دفع",
  tin_card: "شهادة الرقم الضريبي TIN",
  national_id: "البطاقة القومية / جواز السفر",
  assessment: "إشعار ربط ضريبي",
  customs_declaration: "بيان جمركي TANCIS++",
  filing_form: "نموذج إقرار ضريبي",
  invoice: "فاتورة ضريبية",
  statutory_act: "قانون ضريبي",
  portal_screenshot: "لقطة شاشة بوابة الضرائب e-Tax",
  generic: "مستند",
};

const DOC_TYPE_LABELS_PGA: Record<string, string> = {
  receipt: "Isal ta Dafa",
  tin_card: "Shahada ta TIN",
  national_id: "Jinsiyya / Jawaz",
  assessment: "Rabit ta Dariba",
  customs_declaration: "Bayan ta Jamarik",
  filing_form: "Form ta Iqrar",
  invoice: "Fatura ta Dariba",
  statutory_act: "Qanun ta Dariba",
  portal_screenshot: "Sura ta Mawqi SSRA e-Tax",
  generic: "Waraga",
};

export function formatDocType(docType?: string, locale: LocaleCode | string = "en"): string {
  if (!docType) return "Document";
  const loc = locale.toLowerCase();
  if (loc === "ar") {
    return DOC_TYPE_LABELS_AR[docType] ?? DOC_TYPE_LABELS_EN[docType] ?? "مستند";
  }
  if (loc === "pga") {
    return DOC_TYPE_LABELS_PGA[docType] ?? DOC_TYPE_LABELS_EN[docType] ?? "Waraga";
  }
  return DOC_TYPE_LABELS_EN[docType] ?? "Document";
}

export function buildDocumentInspectionModalView(
  doc: {
    readonly id: string;
    readonly name: string;
    readonly sizeBytes?: number | undefined;
    readonly docType?: string | undefined;
    readonly analysis?: DocumentAnalysisData | undefined;
  },
  locale: LocaleCode = "en",
) {
  const analysis = doc.analysis;
  const recon = analysis?.taxReconciliation;
  const fields = analysis?.fields;
  const docType = doc.docType ?? analysis?.docType ?? "generic";
  const sg = analysis?.screenshot_guidance;

  const quickPrompts: string[] = [];
  if (sg?.is_screenshot) {
    const portalName = sg.detected_portal ?? "SSRA e-Tax Portal";
    quickPrompts.push(`Explain the issue shown on this ${portalName} screen.`);
    quickPrompts.push(`Give me step-by-step instructions to complete this ${portalName} action.`);
  }
  if (fields?.tins && fields.tins.length > 0) {
    quickPrompts.push(`Verify taxpayer TIN ${fields.tins[0]} and explain filing obligations.`);
  }
  if (recon?.status === "discrepancy_detected") {
    quickPrompts.push(`Explain the SSP tax arithmetic discrepancy in ${doc.name}.`);
  } else if (docType === "invoice" || docType === "receipt") {
    quickPrompts.push("Confirm if 18% Sales Tax and cash-free bank remittance rules apply here.");
  } else if (docType === "assessment") {
    quickPrompts.push(
      "What are the 30-day deadline and procedure to object to this SSRA tax assessment?",
    );
  } else if (!sg?.is_screenshot) {
    quickPrompts.push(
      "Summarize the key South Sudan tax implications and next steps for this document.",
    );
  }

  const normalizedSteps = (sg?.steps ?? []).map((s) => stripStepPrefix(s));

  return {
    labelledBy: "doc-modal-title",
    initialFocusAttr: "data-dialog-initial-focus",
    title: doc.name,
    typeBadge: formatDocType(docType, locale),
    sizeBadge: doc.sizeBytes != null ? formatFileSize(doc.sizeBytes) : null,
    confidenceBadge:
      analysis?.confidence != null ? `${Math.round(analysis.confidence * 100)}% match` : null,
    isScreenshot: Boolean(sg?.is_screenshot),
    portalUrl: sg?.portal_url ?? "https://etax.nra.gov.ss/",
    normalizedSteps,
    hotspots: sg?.hotspots ?? [],
    reconciliationStatus: recon?.status ?? null,
    quickPrompts,
  };
}
