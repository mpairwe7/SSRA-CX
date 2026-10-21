/**
 * Taxpayer Document & Screenshot Inspection Modal & Attachment Helpers (`packages/chat-ui/src/document-analysis.ts`).
 *
 * Ported from `FinalYearProject/App/frontend/src/lib/attachments.ts` &
 * `src/components/DocumentInspectionModal.tsx`, adapted for South Sudan Revenue Authority (SSRA / NRA):
 * - `stripStepPrefix`: prevents duplicate numbering ("1. Step 1: Click…") in `<ol>` lists.
 * - `formatDocType`: multilingual labels across `en`, `ar`, and `pga`.
 * - `buildDocumentInspectionModalView`: builds attachment metadata and an explicit
 *   unavailable state until approved scanning, OCR, and legal-guidance providers exist.
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
  },
  locale: LocaleCode = "en",
) {
  const docType = doc.docType ?? "generic";
  return {
    labelledBy: "doc-modal-title",
    initialFocusAttr: "data-dialog-initial-focus",
    title: doc.name,
    typeBadge: formatDocType(docType, locale),
    sizeBadge: doc.sizeBytes != null ? formatFileSize(doc.sizeBytes) : null,
    analysisStatus: "unavailable" as const,
    isScreenshot: false,
    portalUrl: null,
    normalizedSteps: [] as string[],
    hotspots: [] as const,
    reconciliationStatus: null,
    quickPrompts: [] as string[],
  };
}
