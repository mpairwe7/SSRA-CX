# ADR-029: Client-Side Document Intake Preflight, BiDi/PDF/Macro Guards, and Truthful OQ-017 Inspection & Receipt UX

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Low–Medium
- **Related:** [ADR-019](./0019-fail-closed-reference-runtime-mode.md), [ADR-023](./0023-public-chat-render-boundary-and-truthful-failure-states.md), [ADR-028](./0028-multiturn-continuity-and-toolathlon-orchestration-hardening.md), [Open Questions (`OQ-017`)](../open-questions.md)

## Context

Comparing the `FinalYearProject` (`ChatInput.tsx`, `DocumentInspectionModal.tsx`, `CameraCapture.tsx`, `attachments.ts`, `pdf_guards.py`) document attachment, inspection, and report flows against `SSRA Assist` (`apps/web/server.js`, `packages/chat-ui/src/document-analysis.ts`, `services/api/src/ssra_api/identity_link/`) identified two sets of requirements that must be satisfied together:

1. **Governance & Truthfulness Invariant (`OQ-017`, Principle 10 & 11):**
   - Server-side `/v1/identity-link/document-precheck` and `/v1/identity-link/documents/analyze` must continue to fail closed with `503 UPSTREAM_UNAVAILABLE` until SSRA approves malware scanning, OCR provenance, retention, and legal snapshot rules (`OQ-017`). The UI must never claim a clean server malware scan, fabricate OCR text, or invent tax reconciliation numbers.
2. **Missing Composer Attachment UX & Client-Side Intake Hardening (`apps/web/server.js` & `@ssra/chat-ui`):**
   - `apps/web/server.js` lacked the main-composer `+` attachment button (`#composer-add-btn`), attachment options modal (`Upload a file or screenshot` / `Take a photo`), attachment chip tray (`#composer-attachments`), `DocumentInspectionModal` (`#doc-inspect-modal-backdrop`), and inspection receipt download (`#doc-modal-report-btn`).
   - `packages/chat-ui/src/document-analysis.ts` lacked client-side intake preflight helpers against Unicode Right-to-Left Override (`U+202E`) filename spoofing, macro-enabled Office containers (`.xlsm`, `.docm`, `.pptm`), polyglot/encrypted/JavaScript-bearing PDFs (`%PDF-` magic header, `/JavaScript`, `/Launch`, `/EmbeddedFiles`, `/XFA`, `/Encrypt`), and indirect prompt injection (`ASI01`).

## Options Considered

1. **Simulate server-side OCR and tax reconciliation in `apps/web/server.js` or `services/api`.** Rejected: violates Principle 10 & 11, `ADR-019`, `ADR-023`, and `OQ-017` by presenting unverified OCR or synthetic tax calculations as live analysis.
2. **Omit attachment and document inspection UI from `apps/web/server.js` entirely.** Rejected: leaves the main chat composer without the `FinalYearProject` attachment, inspection, suggested-prompt, and receipt-export UX.
3. **Integrate the `FinalYearProject` composer attachment, inspection modal, camera dialog, and receipt download flows backed by deterministic client-side format/security preflight and explicit `OQ-017` truthfulness disclosures (chosen).**

## Decision

1. **Hardened Document Intake & Security Preflight (`packages/chat-ui/src/document-analysis.ts`):**
   - `sanitizeAttachmentFilename`: strips path traversal segments, NUL bytes, control characters, and Unicode BiDi override characters (`U+202A..U+202E`).
   - `detectAttachmentKind`: enforces extension-authoritative classification and blocks macro-enabled Office containers (`.xlsm`, `.docm`, `.pptm` -> `MACRO_OFFICE_REJECTED`) and legacy binary `.xls` (`LEGACY_XLS_REJECTED`).
   - `inspectPdfBytesClientPreflight`: requires an ISO 32000-1 `%PDF-` magic header within the first 8 whitespace bytes and rejects `/Encrypt` as well as active/embedded PDF tokens (`/JavaScript`, `/JS`, `/Launch`, `/SubmitForm`, `/ImportData`, `/GoToR`, `/RichMedia`, `/EmbeddedFiles`, `/XFA`).
   - `scrubDocumentTextForIndirectInjection`: strips BiDi/zero-width controls, redacts `ASI01` prompt-injection directives (`[REDACTED_DOCUMENT_INSTRUCTION]`), and masks raw TINs/`+211` phone numbers.
   - `classifySsraDocumentType`, `inspectOfficeZipClientPreflight`, `reconcileClientDocumentText`, `diagnoseSsraPortalScreenshot`, `buildConversationReportExport`, `sanitizeCopilotReturnUrl`, `buildPortalCopilotCardView`, & `buildTruthfulAttachmentReportText`: map attachment names to localized SSRA categories (`en`, `ar`, `pga`), inspect `.docx`/`.xlsx` containers for `PK\x03\x04` ZIP magic and embedded `vbaProject.bin` macros, reconcile plain-text/CSV `Subtotal`/`Tax`/`WHT`/`Total` figures client-side (`oq017ClientOnly: true`), diagnose `e-Tax` and `TANCIS++` screenshots, export PII-redacted conversation reports with integrity digests, and generate a truthful `OQ-017` inspection receipt.
2. **Main Chat Composer Attachment, Inspection, Report Export & 7-Pillar Journey Copilot Flows (`apps/web/server.js`, `packages/ui/icons.js`, `services/agent-runtime/src/ssra_runtime/graphs/guided_journey.py`):**
   - Added `#composer-add-btn` (`+`), `#addmenu-modal-backdrop`, `#composer-attachments` chip bar, `#doc-inspect-modal-backdrop` (with `#doc-modal-copilot-steps` Co-Pilot steps and `#doc-modal-report-btn`), `#export-conv-report-btn` (`Download conversation report` in `#acct-popover`), `#camera-modal-backdrop`, and the 7 Journey Copilot pillars (`evaluate_journey_prerequisites`, `build_journey_form_draft_surface`, `infer_taxpayer_journey_objective`, `evaluate_journey_step_up_auth`, `elevate_anonymous_journey_slots`, `build_journey_stall_scaffolding`, `generate_ssra_resume_code` / `parse_ssra_resume_code`, and `diagnose_ssra_portal_error`).

## Consequences

- Taxpayers can attach up to 3 files (`<= 40 MB`), inspect client-side security preflight results and SHA-256 integrity hashes in `DocumentInspectionModal`, download a truthful inspection receipt, and trigger grounded `T0` public guidance prompts without any fake OCR or unverified statutory math.
- Macro-enabled Office files, polyglot/active-content PDFs, and BiDi-spoofed filenames are deterministically rejected in client preflight.

## Reversal Cost

Low–Medium. When `OQ-017` is closed with approved malware scanning and OCR providers, `buildDocumentInspectionModalView` and `/v1/identity-link/documents/analyze` can transition from `"unavailable"` to verified provider outputs without changing the composer or modal structure.

## Verification

Covered by `packages/chat-ui/tests/chat-ui.test.ts`, `apps/web/tests/web.test.ts`, and `tests/browser/public-chat-a11y.spec.ts`.
