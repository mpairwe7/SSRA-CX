# SSRA Assist — MCP Tool Catalog & Server Authoring Guide (`docs/mcp/README.md`)

**Status:** Draft v1 (Phase 0)  
**Date:** 2026-10-16  
**Protocol Baseline:** MCP Revision `2026-07-28` (Stateless Streamable HTTP, JSON Schema `2020-12`)  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Section 8; [`ADR-004`](../adr/0004-mcp-2026-07-28-and-agentgateway-egress.md)

---

## 1. Protocol & Security Rules for All MCP Servers

1. **Stateless Revision `2026-07-28`:** No `initialize` handshake session. Every HTTP POST to `/mcp` carries `_meta.protocolVersion = "2026-07-28"`, W3C `traceparent`, and is routed by `agentgateway` using `Mcp-Method` and `Mcp-Name` headers.
2. **JSON Schema `2020-12`:** Every tool declares strict `inputSchema` and `outputSchema` (`$schema: "https://json-schema.org/draft/2020-12/schema"`, `additionalProperties: false`) and returns `structuredContent`.
3. **Truthful Tool Annotations:** Every tool sets `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint`, which `agentgateway` enforces alongside `ai/policies/risk-tiers.yaml`.
4. **OAuth 2.1, Subject Binding & Progressive Scope Minimization:** Every server validates audience-, RFC 8707 resource-, and least-privilege scope-bound (`mcp:<server>:read`, `mcp:<server>:write`, `mcp:<server>:step_up`) JWTs issued via `agentgateway`. `T1`–`T3` tools extract `subject_ref` from the RFC 8693 exchanged token—never from LLM-supplied arguments—and enforce state-handle ownership (`taskId`, `appointment_id`, `case_id`). `validate_mcp_oauth_url` blocks SSRF against private/cloud-metadata IP ranges (`RFC 9728 §7.7`).
5. **Confirmation & Payload-Bound Idempotency:** All `T2` and `T3` state-changing tools require `idempotency_key` (bound to `action_digest` with `422` rejection on mutated argument replay and bounded FIFO cache `MAX_MCP_IDEMPOTENT_CACHE = 1024`) and a single-use, short-TTL `confirmation_token` bound to `sha256(tool_name + canonical_args + subject_ref)`.
6. **Provenance, OpenTelemetry MCP Spans & Typed Errors:** Every response wraps payload data with `provenance: { system, record_id, retrieved_at, as_of }` (using `Africa/Juba` `juba_today()`), `data_classification: "PUBLIC" | "CONFIDENTIAL_TAXPAYER" | "INTERNAL_STAFF"`, and OpenTelemetry `semantic-conventions-genai` MCP attributes (`mcp.method.name`, `mcp.protocol.version`, `mcp.server.name`, `gen_ai.operation.name = "execute_tool"`). Errors use only the canonical codes: `NOT_FOUND`, `NOT_AUTHORIZED`, `STEP_UP_REQUIRED`, `UPSTREAM_UNAVAILABLE`, `VALIDATION_FAILED`, `RATE_LIMITED`.

---

## 2. Complete Initial MCP Server & Tool Catalog

| Server (`Mcp-Name`) | Tool (`verb_noun`) | Tier | `readOnlyHint` | `idempotentHint` | Backed By | Phase |
|---|---|---|---|---|---|---|
| **`knowledge`** | `search_knowledge` | `T0` | `true` | `true` | PostgreSQL 18 FTS + `pgvector` HNSW | Phase 0/1 |
| **`knowledge`** | `get_section` | `T0` | `true` | `true` | PostgreSQL 18 (`knowledge_chunks`) | Phase 0/1 |
| **`knowledge`** | `list_forms` | `T0` | `true` | `true` | PostgreSQL 18 (`knowledge_documents`) | Phase 0/1 |
| **`knowledge`** | `get_office_info` | `T0` | `true` | `true` | PostgreSQL 18 (Office Directory) | Phase 0/1 |
| **`tax-facts`** | `get_tax_fact` | `T0` | `true` | `true` | `libs/ssra_rules` + `tax_facts` | Phase 0/1 |
| **`tax-facts`** | `list_tax_facts` | `T0` | `true` | `true` | `libs/ssra_rules` + `tax_facts` | Phase 0/1 |
| **`tax-facts`** | `calculate_paye_estimate` | `T0` | `true` | `true` | `libs/ssra_rules` (Deterministic) | Phase 0/1 |
| **`tax-facts`** | `calculate_withholding_estimate` | `T0` | `true` | `true` | `libs/ssra_rules` (Deterministic) | Phase 0/1 |
| **`official-channels`** | `verify_payment_account` | `T0` | `true` | `true` | Signed Official-Channel Registry | Phase 0/1 |
| **`official-channels`** | `verify_sender` | `T0` | `true` | `true` | Signed Official-Channel Registry | Phase 0/1 |
| **`official-channels`** | `report_scam` | `T2` | `false` | `true` | Case Service (`SCAM_REPORT`) | Phase 1 |
| **`taxpayer`** | `verify_tin` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`taxpayer`** | `get_registration_status` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`taxpayer`** | `get_profile_masked` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`ledger`** | `get_filing_status` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`ledger`** | `list_assessments` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`ledger`** | `get_balance` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`ledger`** | `list_payments` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`payments-info`** | `list_payment_channels` | `T0` | `true` | `true` | Official-Channel Registry + BoSS | Phase 1 |
| **`payments-info`** | `get_payment_instructions` | `T0` | `true` | `true` | Official-Channel Registry + e-Tax | Phase 1 |
| **`payments-info`** | `generate_payment_reference`* | `T3` | `false` | `true` | `ETaxPort` (Disabled until `OQ-006`) | Phase 2* |
| **`tcc`** | `get_tcc_status` | `T1` | `true` | `true` | `ETaxPort` (`libs/ssra_adapters`) | Phase 2 |
| **`tcc`** | `request_tcc`* | `T3` | `false` | `true` | `ETaxPort` (Disabled until `OQ-001`) | Phase 2* |
| **`customs`** | `lookup_tariff` | `T0` | `true` | `true` | `ECustomsPort` (`OQ-002`) | Phase 2 |
| **`customs`** | `estimate_duties` | `T0` | `true` | `true` | `ECustomsPort` + BoSS Official Rate | Phase 2 |
| **`customs`** | `get_declaration_status` | `T1` | `true` | `true` | `ECustomsPort` (`OQ-002`) | Phase 2 |
| **`cases`** | `create_case` | `T2` | `false` | `true` | `services/api` (`cases`) | Phase 1/2 |
| **`cases`** | `get_case_status` | `T1` | `true` | `true` | `services/api` (`cases`) | Phase 2 |
| **`cases`** | `add_case_note` | `T2` | `false` | `true` | `services/api` (`cases`) | Phase 2 |
| **`appointments`** | `list_slots` | `T0` | `true` | `true` | `services/api` (`appointments`) | Phase 2 |
| **`appointments`** | `book_appointment` | `T2` | `false` | `true` | `services/api` (`appointments`) | Phase 2 |
| **`appointments`** | `cancel_appointment` | `T2` | `false` | `true` | `services/api` (`appointments`) | Phase 2 |
| **`notifications`** | `send_template_message` | `T2` | `false` | `true` | `services/channel-gateway` (Staff/Sys) | Phase 3/4 |

*\* Marked tools remain disabled behind feature flags until SSRA confirms upstream API availability and authorisation (`OQ-001`, `OQ-006`).*
