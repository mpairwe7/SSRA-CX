/**
 * Taxpayer Document & Screenshot Inspection Modal, Security Preflight & Report Helpers
 * (`packages/chat-ui/src/document-analysis.ts`).
 *
 * Adapted from `FinalYearProject/App/frontend/src/lib/attachments.ts`,
 * `src/components/DocumentInspectionModal.tsx`, and `App/backend/app/pdf_guards.py`
 * for the South Sudan Revenue Authority (SSRA / NRA) under OQ-017 governance:
 * - `sanitizeAttachmentFilename`: strips path segments, NULs, and BiDi override characters (`U+202A..U+202E`).
 * - `detectAttachmentKind`: extension-authoritative classification blocking `.xlsm`/`.docm`/`.pptm` macros and legacy `.xls`.
 * - `inspectPdfBytesClientPreflight`: ISO 32000-1 `%PDF-` header check + active content (`/JavaScript`, `/Launch`, `/EmbeddedFiles`, `/XFA`) & `/Encrypt` detection.
 * - `scrubDocumentTextForIndirectInjection`: strips BiDi/zero-width controls, scrubs indirect prompt injection (`ASI01`), and masks raw TINs/`+211` phones.
 * - `buildDocumentInspectionModalView` & `buildTruthfulAttachmentReportText`: truthful `OQ-017` unavailable state for server OCR/malware scanning alongside verified client preflight metadata.
 */

import type { LocaleCode } from "@ssra/contracts";

export const MAX_ATTACHMENTS_PER_TURN = 3;
export const MAX_ATTACHMENT_BYTES = 40 * 1024 * 1024;
export const ATTACHMENT_ACCEPT = ".pdf,.docx,.xlsx,.csv,.txt,image/*";
export const THUMBNAIL_EDGE_PX = 56;

const SAFE_DATA_IMAGE_RE = /^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/;
const BIDI_AND_ZERO_WIDTH_RE = /[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g;
const FILENAME_UNSAFE_RE = /[^\p{L}\p{N}.\- ()[\]_]+/gu;

function stripControlChars(input: string, allowNewlines = false): string {
  let out = "";
  for (let i = 0; i < input.length; i += 1) {
    const code = input.charCodeAt(i);
    if (
      (code >= 32 && code !== 127) ||
      (allowNewlines && (code === 9 || code === 10 || code === 13))
    ) {
      out += input[i];
    }
  }
  return out.replace(BIDI_AND_ZERO_WIDTH_RE, "");
}
const DANGEROUS_PDF_TOKEN_RE =
  /\/(?:JavaScript|JS|Launch|SubmitForm|ImportData|GoToR|RichMedia|EmbeddedFiles|XFA)\b/g;
const PDF_ENCRYPT_TOKEN_RE = /\/Encrypt\b/;
const INDIRECT_INJECTION_RE =
  /(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|system\s+prompt\s*:|<\|im_start\|>|<\|endoftext\|>|<\s*\/?\s*untrusted_)/gi;
const RAW_TIN_RE = /\b(\d{6})(\d{4})\b/g;
const RAW_PHONE_211_RE = /\+211[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d(\d{2})\b/g;

export type AttachmentKind = "pdf" | "docx" | "xlsx" | "csv" | "text" | "image";

export type AttachmentKindResult =
  | { readonly ok: true; readonly kind: AttachmentKind }
  | {
      readonly ok: false;
      readonly reason: "MACRO_OFFICE_REJECTED" | "LEGACY_XLS_REJECTED" | "UNSUPPORTED_EXTENSION";
      readonly message: string;
    };

export interface PdfPreflightResult {
  readonly ok: boolean;
  readonly encrypted: boolean;
  readonly findings: readonly string[];
}

const KIND_BY_EXTENSION: ReadonlyArray<readonly [string, AttachmentKind]> = [
  [".pdf", "pdf"],
  [".docx", "docx"],
  [".xlsx", "xlsx"],
  [".csv", "csv"],
  [".txt", "text"],
  [".png", "image"],
  [".jpg", "image"],
  [".jpeg", "image"],
  [".webp", "image"],
  [".bmp", "image"],
  [".tiff", "image"],
];

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

/**
 * Drop path segments, NUL bytes, and Unicode BiDi override characters (blocking RLO extension spoofing).
 */
export function sanitizeAttachmentFilename(filename: string): string {
  const raw = stripControlChars(String(filename || "document"), false).replace(/\\/g, "/");
  const base = raw.split("/").pop() || "document";
  const cleaned = base.replace(FILENAME_UNSAFE_RE, "_").replace(/^[.\s]+|[.\s]+$/g, "");
  return cleaned.slice(0, 120) || "document";
}

/**
 * Map a filename/MIME pair to an allowed attachment kind, rejecting macro-enabled Office files and legacy `.xls`.
 */
export function detectAttachmentKind(filename: string, contentType = ""): AttachmentKindResult {
  const lower = sanitizeAttachmentFilename(filename).toLowerCase();
  if (lower.endsWith(".xlsm") || lower.endsWith(".docm") || lower.endsWith(".pptm")) {
    return {
      ok: false,
      reason: "MACRO_OFFICE_REJECTED",
      message:
        "Macro-enabled Office documents (.xlsm, .docm, .pptm) are blocked for security. Re-save as .xlsx or .docx.",
    };
  }
  if (lower.endsWith(".xls")) {
    return {
      ok: false,
      reason: "LEGACY_XLS_REJECTED",
      message: "Legacy .xls workbooks are not accepted. Re-save as .xlsx.",
    };
  }
  for (const [ext, kind] of KIND_BY_EXTENSION) {
    if (lower.endsWith(ext)) {
      return { ok: true, kind };
    }
  }
  if (!lower.includes(".")) {
    const ctype = contentType.split(";")[0]?.trim().toLowerCase() ?? "";
    if (ctype.startsWith("image/")) return { ok: true, kind: "image" };
    if (ctype === "application/pdf") return { ok: true, kind: "pdf" };
  }
  return {
    ok: false,
    reason: "UNSUPPORTED_EXTENSION",
    message: "Unsupported file type. Allowed: .pdf, .docx, .xlsx, .csv, .txt, and images.",
  };
}

/**
 * Perform structural PDF byte preflight (ISO 32000-1 `%PDF-` magic header, encryption, and active-content tokens).
 */
export function inspectPdfBytesClientPreflight(bytes: Uint8Array): PdfPreflightResult {
  if (!bytes || bytes.byteLength === 0) {
    return { ok: false, encrypted: false, findings: ["Empty PDF file."] };
  }
  let offset = 0;
  const maxLead = Math.min(bytes.byteLength, 8);
  while (
    offset < maxLead &&
    (bytes[offset] === 0x20 ||
      bytes[offset] === 0x09 ||
      bytes[offset] === 0x0d ||
      bytes[offset] === 0x0a)
  ) {
    offset += 1;
  }
  const hasPdfMagic =
    bytes.byteLength >= offset + 5 &&
    bytes[offset] === 0x25 && // %
    bytes[offset + 1] === 0x50 && // P
    bytes[offset + 2] === 0x44 && // D
    bytes[offset + 3] === 0x46 && // F
    bytes[offset + 4] === 0x2d; // -
  if (!hasPdfMagic) {
    return {
      ok: false,
      encrypted: false,
      findings: [
        "File content does not start with a valid %PDF- header (polyglot or corrupted file rejected).",
      ],
    };
  }

  const scanSlice = bytes.subarray(0, Math.min(bytes.byteLength, 512 * 1024));
  const latin1 = new TextDecoder("latin1").decode(scanSlice);
  const findings: string[] = [];
  const encrypted = PDF_ENCRYPT_TOKEN_RE.test(latin1);
  if (encrypted) {
    findings.push("Encrypted or password-protected PDF documents are not accepted.");
  }
  const seenTokens = new Set<string>();
  for (const match of latin1.matchAll(DANGEROUS_PDF_TOKEN_RE)) {
    const tok = match[0];
    if (tok && !seenTokens.has(tok)) {
      seenTokens.add(tok);
      findings.push(`PDF contains active or embedded content (${tok}).`);
    }
  }
  return {
    ok: findings.length === 0,
    encrypted,
    findings,
  };
}

/**
 * Strip BiDi/zero-width control characters, scrub indirect prompt-injection directives (`ASI01`), and mask TIN/`+211` PII.
 */
export function scrubDocumentTextForIndirectInjection(rawText: string): {
  readonly cleanedText: string;
  readonly injectionScrubbed: boolean;
  readonly piiRedacted: boolean;
} {
  const noBidi = stripControlChars(String(rawText || ""), true);
  let injectionScrubbed = false;
  const afterInj = noBidi.replace(INDIRECT_INJECTION_RE, () => {
    injectionScrubbed = true;
    return "[REDACTED_DOCUMENT_INSTRUCTION]";
  });
  let piiRedacted = false;
  const afterTin = afterInj.replace(RAW_TIN_RE, (_m, _prefix, last4) => {
    piiRedacted = true;
    return `••••${last4}`;
  });
  const afterPhone = afterTin.replace(RAW_PHONE_211_RE, (_m, last2) => {
    piiRedacted = true;
    return `+211•••••••${last2}`;
  });
  return {
    cleanedText: afterPhone.slice(0, 4000).trim(),
    injectionScrubbed,
    piiRedacted,
  };
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

/**
 * Classify a filename and optional text sample into an SSRA document category and return public T0 suggested prompts.
 */
export function classifySsraDocumentType(
  filename: string,
  textSample = "",
): { readonly docType: string; readonly suggestedPublicPrompts: readonly string[] } {
  const combined = `${sanitizeAttachmentFilename(filename)} ${textSample}`.toLowerCase();
  if (/(?:screenshot|screen|portal|etax|error|capture|snip)/.test(combined)) {
    return {
      docType: "portal_screenshot",
      suggestedPublicPrompts: [
        "Where can I find general e-Tax filing guidance?",
        "Is https://etax.nra.gov.ss/ an official SSRA payment portal?",
      ],
    };
  }
  if (/(?:customs|declaration|tancis|asycuda|nimule|hs\s*\d{4})/.test(combined)) {
    return {
      docType: "customs_declaration",
      suggestedPublicPrompts: [
        "Where can I find general customs guidance?",
        "What is the customs tariff rate for HS 8703.23?",
      ],
    };
  }
  if (/(?:tin|registration|certificate)/.test(combined)) {
    return {
      docType: "tin_card",
      suggestedPublicPrompts: [
        "How do I register for a TIN on e-Tax?",
        "Where can I find general e-Tax filing guidance?",
      ],
    };
  }
  if (/(?:receipt|payment|bank|remittance)/.test(combined)) {
    return {
      docType: "receipt",
      suggestedPublicPrompts: [
        "Verify account TSA-ETAX-BANK for tax payment",
        "How do I file and pay my tax return on e-Tax?",
      ],
    };
  }
  if (/(?:invoice|wht|withholding)/.test(combined)) {
    return {
      docType: "invoice",
      suggestedPublicPrompts: [
        "Calculate withholding tax on 1,000,000 SSP for rent",
        "Where can I find general e-Tax filing guidance?",
      ],
    };
  }
  if (/(?:assessment|demand|notice)/.test(combined)) {
    return {
      docType: "assessment",
      suggestedPublicPrompts: [
        "How do I file and pay my tax return on e-Tax?",
        "I would like to speak with an SSRA tax officer",
      ],
    };
  }
  return {
    docType: "generic",
    suggestedPublicPrompts: [
      "Where can I find general e-Tax filing guidance?",
      "How do I register for a TIN on e-Tax?",
    ],
  };
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
    title: sanitizeAttachmentFilename(doc.name),
    typeBadge: formatDocType(docType, locale),
    sizeBadge: doc.sizeBytes != null ? formatFileSize(doc.sizeBytes) : null,
    analysisStatus: "unavailable" as const,
    unavailableNotice:
      "Automated OCR, malware scanning, and tax reconciliation are unavailable until SSRA approves OQ-017 providers. Do not upload confidential taxpayer records in public chat.",
    isScreenshot: false,
    portalUrl: null,
    normalizedSteps: [] as string[],
    hotspots: [] as const,
    reconciliationStatus: null,
    quickPrompts: [] as string[],
  };
}

/**
 * Generate a truthful client-side attachment preflight inspection report receipt (OQ-017 compliant).
 */
export function buildTruthfulAttachmentReportText(input: {
  readonly id: string;
  readonly name: string;
  readonly sizeBytes: number;
  readonly docType: string;
  readonly sha256Hex?: string | undefined;
  readonly preflightStatus: "passed" | "warning" | "blocked";
  readonly preflightFindings?: readonly string[] | undefined;
  readonly locale?: LocaleCode | undefined;
}): string {
  const safeName = sanitizeAttachmentFilename(input.name);
  const typeLabel = formatDocType(input.docType, input.locale ?? "en");
  const sizeLabel = formatFileSize(input.sizeBytes);
  const findings = input.preflightFindings?.length
    ? input.preflightFindings.map((f, i) => `  ${i + 1}. ${f}`).join("\n")
    : "  None (client-side extension and header preflight passed).";
  return [
    "========================================================================",
    "SOUTH SUDAN REVENUE AUTHORITY (SSRA) — ATTACHMENT PREFLIGHT RECEIPT",
    "========================================================================",
    `Attachment ID     : ${input.id}`,
    `File Name         : ${safeName}`,
    `Detected Category : ${typeLabel} (${input.docType})`,
    `File Size         : ${sizeLabel} (${input.sizeBytes} bytes)`,
    `SHA-256 Digest    : ${input.sha256Hex || "not_computed"}`,
    `Client Preflight  : ${input.preflightStatus.toUpperCase()}`,
    "Preflight Notes   :",
    findings,
    "------------------------------------------------------------------------",
    "GOVERNANCE & TRUTHFULNESS NOTICE (OQ-017):",
    "Server-side OCR extraction, malware scanning, and automated tax figure",
    "reconciliation are currently disabled until SSRA approves OQ-017",
    "providers and legal snapshot rules. This receipt records client-side",
    "file metadata only and is NOT an official SSRA tax assessment or",
    "verification certificate. Official e-Tax portal: https://etax.nra.gov.ss/",
    "========================================================================",
  ].join("\n");
}
