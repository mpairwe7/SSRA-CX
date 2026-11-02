# ADR-030: Agentic Tool Security, Verification, and Reliability Hardening Across Search, API/MCP, Execution, Database, File, and Web/Channel Tools

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-11-02
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Low–Medium
- **Related:** [ADR-004](./0004-mcp-2026-07-28-and-agentgateway-egress.md), [ADR-008](./0008-risk-tiered-autonomy-subject-binding-and-opa.md), [ADR-009](./0009-deterministic-tax-facts-registry-and-numeric-provenance.md), [ADR-028](./0028-multiturn-continuity-and-toolathlon-orchestration-hardening.md), [ADR-029](./0029-document-intake-preflight-and-truthful-inspection-ux.md)

## Context and Problem Statement

A November 2026 quality-assurance, security, and reliability audit across all six AI agentic tool categories in `SSRA Assist` (`Search`, `API/MCP Gateway`, `Code/Rule/Sandbox Execution`, `Database/State/Memory`, `File/Document Intake`, and `Web/Portal/Channel Automation`)—benchmarked against the NSA/CISA *Model Context Protocol (MCP): Security Design* guidance (`CSI_MCP_SECURITY.PDF`, June 2026), Cloud Security Alliance *MCP Security Crisis* research (May 2026), `arXiv:2603.13417v1` (*Design Patterns for Deploying AI Agents with MCP*), and OWASP Top 10 for Agentic Applications 2026 (`ASI01`–`ASI10`)—identified twelve primary and six second-order gaps:

1. **Search & Retrieval Tools (`mcp-servers/knowledge`, `services/agent-runtime/src/ssra_runtime/retrieval/*`):**
   - `KnowledgeCorpusAdapter.get_section` and `get_document_section` did not enforce `self.is_temporally_valid(chk, target_date)`, allowing direct lookup of repealed/superseded statutory chunks (`chk-superseded-2009-paye`).
   - `postprocess_retrieved_chunks` (`hybrid.py`) used a static fallback date and discarded the return value of `detect_conflicting_chunks(filtered)` instead of quarantining conflicting active `(section_anchor, language)` chunks.
   - `KnowledgeCorpusAdapter.search_knowledge` did not expand Nilotic/Arabic/Juba Arabic termbase entries from `ai/termbase/glossary.yaml` or deduplicate repeated query tokens against repetition-stuffing score manipulation.
2. **API & MCP Gateway Tools (`libs/ssra_mcp`, `services/agent-runtime/src/ssra_runtime/tools/mcp_client.py`):**
   - `StatelessMcpServer.handle_call_tool` did not bound JSON argument nesting depth (`MAX_MCP_ARG_DEPTH = 8`) or total key count (`MAX_MCP_ARG_KEYS = 64`) before schema validation, and returned mutable references from `_idempotent_cache` without TTL expiration.
   - `GovernedMcpGatewayClient.invoke_tool` did not deep-copy turn-memoized read artifacts (`budget.memoized_read_artifacts`) or verify non-empty `provenance.record_id` / `provenance.as_of` post-conditions, and `sanitiser.py` lacked ANSI/VT100 terminal escape stripping and `trade.eservices.gov.ss` in `ALLOWED_SSRA_DOMAINS`.
3. **Code / Rule / Sandbox Execution Tools (`services/agent-runtime/src/ssra_runtime/nodes/verifier.py`, `packages/chat-ui/src/mcp-apps-sandbox.ts`):**
   - `_detect_quiet_tool_fault` checked top-level bounds on `calculate_paye_estimate`, `calculate_withholding_estimate`, and `estimate_duties`, but did not verify that PAYE `bands` sum to `gross_monthly_ssp` and `estimated_tax_ssp`, that WHT equals `gross * rate / 100`, or that customs `customs_value_ssp` and `estimated_duty_ssp` match `cif_value_usd * boss_official_fx_rate_ssp_per_usd * duty_rate_percent / 100`.
   - `validateMcpAppIframe` did not block embedded credentials, non-443 ports, encoded traversal (`%2e`), or `javascript:`/`data:` parameters, and did not attach explicit `allowAttr` (`Permissions-Policy`) and `cspAttr` isolation descriptors.
4. **Database & State Tools (`services/api/src/ssra_api/repositories.py`, `mcp-servers/appointments`, `mcp-servers/cases`):**
   - `PostgresRlsSessionContext.to_set_local_sql` did not validate `staff_id`, set `statement_timeout` / `lock_timeout`, or enforce `SET LOCAL transaction_read_only = on;` for the `auditor` role (`ADR-018` Separation of Duties).
   - `appointments.cancel_appointment` allowed re-cancelling an already-`CANCELLED` appointment without raising `409 CONFLICT`, `book_appointment` did not validate `slot_id` format, and `cases.add_case_note` allowed appending notes to `CLOSED`/`RESOLVED` cases.
5. **File & Document Intake Tools (`apps/web/src/app/api/uploads/route.ts`, `packages/chat-ui/src/document-analysis.ts`):**
   - `validateClientUpload` did not block Unicode BiDi overrides (`U+202E`), double dangerous extensions (`invoice.exe.pdf`), macro extensions (`.xlsm`, `.docm`, `.pptm`, `.xls`), or verify optional `magicBytes` against declared `mimeType`.
6. **Web / Portal & Channel Automation Tools (`libs/ssra_adapters/src/ssra_adapters/ports.py`, `services/channel-gateway/src/ssra_channel_gateway/whatsapp.py`):**
   - `MockOfficialChannelsAdapter.verify_identifier` certified URLs on official domains even when query/fragment parameters contained open-redirect or XSS payloads (`?redirect=https://evil.example`, `?next=//evil.example`).
   - `validate_whatsapp_list_rows` did not enforce unique row IDs, and `prepare_whatsapp_outbound_message` did not verify embedded URLs in `body_text` against `is_allowed_ssra_url`.

## Options Considered

1. **Rely solely on LLM prompt instructions and JSON Schema validation.** Rejected: JSON Schema alone does not enforce bi-temporal supersession, cross-field Decimal arithmetic invariants, open-redirect query inspection, or database transaction read-only/timeout guards.
2. **Enforce deterministic pre-conditions, post-conditions, and isolation guards across all 6 tool categories in 4 phases (chosen).**

## Decision Outcome

1. **Phase 1 (Search & API/MCP Gateway Tools):**
   - Enforce `is_temporally_valid` in `KnowledgeCorpusAdapter.get_section` / `get_document_section`, expand multilingual `glossary.yaml` terms and deduplicate tokens in `search_knowledge` and `rerank_chunks`, and quarantine conflicting active chunks on both `effective_from` and `content` divergence in `postprocess_retrieved_chunks` using `juba_today()`.
   - Enforce `MAX_MCP_ARG_DEPTH = 8`, `MAX_MCP_ARG_KEYS = 64`, `MCP_IDEMPOTENCY_TTL_SECONDS = 86400`, and `copy.deepcopy` cache isolation in `StatelessMcpServer` and `GovernedMcpGatewayClient`, plus CSI/OSC/C1 ANSI escape stripping and URL open-redirect/traversal checks in `sanitiser.py`.
2. **Phase 2 (Code/Rule/Sandbox Execution & Database/State Tools):**
   - Upgrade `_detect_quiet_tool_fault` (`verifier.py`) with finite-Decimal (`is_finite()`) default-`-1` parsing and cross-field Decimal band-sum and rate-product verification across PAYE, WHT, and Customs tools.
   - Harden `validateMcpAppIframe` (`mcp-apps-sandbox.ts`) with credential/port/traversal/scheme checks and locked `allowAttr` + `cspAttr` descriptors.
   - Harden `PostgresRlsSessionContext` (`repositories.py`) with `staff_id` validation, `statement_timeout = '5000ms'`, `lock_timeout = '2000ms'`, and `SET LOCAL transaction_read_only = on;` for `auditor`, and enforce duplicate-booking, closed-case, and re-cancellation conflict (`409`) and PII redaction guards in `appointments` and `cases`.
3. **Phase 3 (File/Document Intake & Web/Portal/Channel Automation Tools):**
   - Harden `validateClientUpload` (`uploads/route.ts`) with BiDi/control-char, double-extension, macro-extension, `ftypavif`/`ftypavis` brand, and polyglot `<script`/`<?php` `magicBytes` signature verification, and unify `inspectOfficeContainerBytesPreflight` and `inspectOfficeZipClientPreflight` in `document-analysis.ts`.
   - Block URL-decoded open-redirect and control-character query/fragment smuggling in `MockOfficialChannelsAdapter.verify_identifier` (`ports.py`), and enforce unique list row IDs and `is_allowed_ssra_url` outbound URL verification in `whatsapp.py`.

## Consequences

- Superseded statutes, conflicting active chunks, open-redirect phishing links on official domains, tampered or `NaN`/corrupted tool arithmetic, deeply nested MCP payloads, and spoofed/polyglot file uploads are deterministically rejected before reaching taxpayers or upstream systems.

## Reversal Cost

Low–Medium. All guards are localized to the tool adapters, MCP base server, verifier node, and intake helpers, and are verified by automated unit and regression suites.

## Confirmation

Covered by `test_agentic_tool_audit_phases_1_to_4_regression` in `evals/suites/test_backend_hardening_and_full_coverage.py`, `packages/chat-ui/tests/chat-ui.test.ts`, and `apps/web/tests/web.test.ts`.
