# SSRA Assist — Open Questions Register (`docs/open-questions.md`)

**Last Updated:** 2026-10-22
**Governance Rule:** Never invent South Sudan tax law, rates, deadlines, penalties, fees, exchange rates, endpoints, or data formats. Whenever an upstream capability, legal rule, or operational parameter is unconfirmed by SSRA, log it here as `OQ-###`, define a clean port interface, build a synthetic mock adapter, and enforce the safest runtime fallback (abstain and offer human handoff).

---

## Summary Table

| ID | Question | Blocks | Owner (SSRA) | Status | Safe Fallback Until Answered |
|---|---|---|---|---|---|
| **OQ-001** | **e-Tax APIs:** endpoints, auth model, rate limits, sandbox, data dictionary, TIN format | Phase 2 | SSRA ICT & Domestic Tax | 🔴 Open | Define `ETaxPort` in `libs/ssra_adapters`; use deterministic mock adapter with synthetic data (`TIN ••••1234`); disable live T1/T3 e-Tax calls. |
| **OQ-002** | **e-Customs platform and APIs:** declaration status, tariff data, HS code schedule | Phase 2 | SSRA Customs & ICT | 🔴 Open | Define `ECustomsPort`; mock adapter returns synthetic test declarations; public assistant answers only published general customs procedures (T0) and hands off specific declaration/tariff queries. |
| **OQ-003** | **Hosting:** NCA data-centre capacity (CPU, GPU, storage, network), DR site, any approved regional cloud | Phase 0 (Sign-off) | SSRA ICT & NCA | 🔴 Open | Standardize operational runbooks and deployments on hardened Docker Compose (`infra/compose/docker-compose.yml` + `infra/compose/docker-compose.prod.yml` with `read_only`, `cap_drop: ["ALL"]`, `no-new-privileges:true`, and `sovereign_internal_net`) sized for modular CPU + single/dual GPU profiles; Kubernetes deployment is decommissioned in operational runbooks. |
| **OQ-004** | **AI providers:** approved external models, data classes allowed to leave the country, zero-retention contracts | Phase 1 | SSRA Management, Legal & SecOps | 🔴 Open | Default all model routing in `ai/routing/` to in-country self-hosted open-weight models (`vLLM`/`SGLang`); keep external provider plug-ins disabled by default behind `agentgateway`. |
| **OQ-005** | **Identity:** civil-registry or national-ID/passport format (`[RP]\d{7,8}`), OTP delivery partners & verification adapter, SIM-swap signals, staff identity provider | Phase 2 | SSRA ICT, SecOps & Telcos | 🔴 Open | `/v1/identity-link/verify-otp` returns 503 until approved providers and durable subject binding exist. No local helper may bind a TIN to a taxpayer identity. |
| **OQ-006** | **Payments:** who may generate payment references, bank and mobile-money partners, Bank of South Sudan integration | Phase 2 | SSRA Finance, BoSS & ICT | 🔴 Open | Provide static, cited instructions for official e-Tax bank remittance only; keep `generate_payment_reference` feature-flagged off (`*` in catalog); never compute FX rates. |
| **OQ-007** | **Channels:** WhatsApp number and verification, SMS sender ID, USSD short code, toll-free voice line, operator agreements | Phase 1 | SSRA Communications & ICT | 🔴 Open | Build against `ChannelPort` with local webhook/SMPP/USSD simulators in `infra/compose/`; populate placeholder sender IDs clearly marked `UNVERIFIED_DEV_ONLY`. |
| **OQ-008** | **Languages:** priority order, translation and review capacity, termbase ownership | Phase 1 | SSRA Communications & Legal | 🔴 Open | Scaffold ICU message catalogs and `ai/termbase/` for `en`, `pga`, and `ar` (RTL) for Phase 1, plus `din`, `nus`, `bfa`, `zne`, `shk` placeholders; require human review sign-off before publishing Tier B/C translations. |
| **OQ-009** | **Legal:** retention schedule, recording consent, taxpayer-secrecy provisions, data-protection bill status, fiscal year confirmation (1 July – 30 June) | Phase 1 | SSRA Legal | 🔴 Open | Enforce GDPR-grade / AU Malabo Convention defaults, strict PII redaction (Presidio), explicit opt-in consent, short default checkpoint TTLs, and require SSRA Legal approval on every `KnowledgeSnapshot` and `TaxFact`. |
| **OQ-010** | **Operations:** contact-centre size and hours, escalation matrix, SLAs, console roles | Phase 1 | SSRA Contact Centre & Operations | 🔴 Open | Configure parameterised office hours (`Africa/Juba`), queues, RBAC roles, and SLA timers in `services/api` and Temporal with conservative defaults; route out-of-hours escalations to callback intake. |
| **OQ-011** | **Official-channel registry and branding** for anti-scam verification | Phase 1 | SSRA Communications & SecOps | 🔴 Open | Seed `official-channels` MCP server with verified domain `etax.nra.gov.ss` and March 2026 cash-free bank-only directive; mark phone/short-code/bank account entries as pending SSRA sign-off. |
| **OQ-012** | **Procurement:** open-source policy, licensing, export-control and sanctions screening of vendors | Phase 0 (Sign-off) | SSRA Procurement & Legal | 🔴 Open | Restrict Phase 0 stack strictly to permissive/open OSI-approved self-hostable software (Apache-2.0, MIT, BSD, PostgreSQL); generate CycloneDX SBOMs for license audit. |
| **OQ-013** | **Production Analytics Warehouse & Workforce Telemetry Aggregation:** ClickHouse / Langfuse warehouse schema & staff AHT baseline for live `AgenticCxScorecard` aggregation | Phase 4 | SSRA Operations & ICT | 🔴 Open | Analytics summary, insight, drift, and scorecard APIs return 503; the staff console remains 403 preview-only until a governed warehouse, freshness rules, and metric provenance are approved. |
| **OQ-014** | **Staff Console Identity, Role Mapping & Session Authorization:** approved IdP, server-side session validation, role claims, step-up requirements and audit attribution | Phase 2 | SSRA ICT, SecOps & Operations | 🔴 Open | Keep the console in non-operational preview mode; deny staff API reads and writes until sessions are server-verified and roles are mapped to approved policy. Never authorize from local storage or `X-SSRA-Staff-Id`. |
| **OQ-015** | **Durable API and conversation state:** authoritative stores, RLS/session context, encryption/retention, checkpoint recovery, and transactional event delivery | Phase 0–3 | SSRA ICT, SecOps & Operations | 🔴 Open | Production mode returns 503 from the API and agent runtime. Use process-local repositories, `InMemorySaver`, and the event buffer only in explicit reference mode; never claim cross-replica continuity or durable delivery. |
| **OQ-016** | **Appointment inventory and booking authority:** office calendars, slot reservation, cancellation, timezone, and conflict/idempotency rules | Phase 2 | SSRA Operations & ICT | 🔴 Open | `GET /v1/appointments/slots` returns 503 until an approved live inventory and booking provider is configured. Do not return fixed sample slots as availability. |
| **OQ-017** | **Document scanning, OCR, and evidence guidance:** approved malware scanner, OCR provenance, retention, source citations, and legal review for any document-derived numeric guidance | Phase 2 | SSRA ICT, SecOps & Legal | 🔴 Open | Document precheck and analysis APIs return 503. Do not report a clean scan, OCR result, statutory rate, deadline, or portal instruction without the corresponding approved provider and source snapshot. |
| **OQ-018** | **Artifact and model trust:** approved registry, signing identity, certificate or Sigstore trust roots, provenance policy, and verification point for images and model artifacts | R1 residual risk and R4 | SSRA ICT, SecOps & Procurement | 🔴 Open | Do not deploy or load a new image or model artifact from an unapproved registry. Keep the production runtime fail closed; use only existing local reference artifacts for development. Gate R1 approval does not close this question. |
| **OQ-019** | **Offline statutory snapshot lifecycle:** publication authority, signed format, legal effective dates, expiry, emergency revocation, and user-facing unavailable state | R2 | SSRA Legal, Domestic Tax, Communications & SecOps | 🔴 Open | Do not ship or expose existing or new browser-side statutory values or official-channel claims until an SSRA-approved signed, versioned, expiring snapshot exists. When current cited evidence is unavailable, direct the user to reconnect or request human assistance. |

---

## Detailed Question Records

### OQ-018 — Artifact and Model Trust
- **Blocks:** production artifact/model release readiness and R4 production deployment; it remains a residual control under the conditional Gate R1 approval.
- **Context:** R0 found partial image pinning, no verified per-image SBOM/signature workflow, no approved deployment verification point, and no evidence that model artifacts are signed before load. R1-A now records a bounded repository security-fix procedure in [`docs/runbooks/dependency-security-exceptions.md`](./runbooks/dependency-security-exceptions.md), but it neither selects an SSRA approval authority nor establishes trust for production artifacts. Selecting trust roots and registry ownership has security and operational reversal cost.
- **Specific Questions for SSRA ICT, SecOps & Procurement:**
  1. Which in-country registry or approved mirror owns container, model, and SBOM distribution for SSRA Assist?
  2. Which identities may sign images, provenance, and models; which certificate or Sigstore roots, expiry rules, and revocation process must consumers trust?
  3. Where must verification occur before an image pull, Compose start, or model load, and what is the approved response to an unsigned, re-tagged, expired, or revoked artifact?
  4. Which security-fix exception process may temporarily override the dependency cooldown, and who approves, records, and expires it?

### OQ-019 — Offline Statutory Snapshot Lifecycle
- **Blocks:** R2 offline statutory experience
- **Context:** The reference chat UI package contains statutory and official-channel values intended for low-connectivity use. R0 found no SSRA-approved publication, signing, expiry, or emergency revocation model for this browser-side data. Existing values must remain excluded from shipped browser experiences, or resolve to a safe unavailable/reconnect or handoff state, until an approved snapshot exists.
- **Specific Questions for SSRA Legal, Domestic Tax, Communications & SecOps:**
  1. Which team approves the exact tax facts, office details, and official-channel entries eligible for an offline snapshot, and what citation/effective-date fields must accompany each record?
  2. What maximum offline validity period, renewal behavior, and emergency revocation mechanism apply when law, official channels, or public guidance change?
  3. Which signature format and trust root may browsers verify without exposing a private key, and how should an invalid or expired snapshot communicate safe next steps in each supported language?
  4. Which accessibility and low-bandwidth requirements apply to the unavailable and reconnect/handoff flow?

### OQ-014 — Staff Console Identity, Role Mapping & Session Authorization
- **Blocks:** Phase 2 (Operational Staff Console)
- **Context:** The current server-rendered console has no verified staff session. A browser-selected role or caller-supplied staff ID cannot prove identity or permission. Staff screens remain a navigation preview and staff API routes fail closed until this decision is approved.
- **Specific Questions for SSRA ICT, SecOps & Operations:**
  1. Which staff identity provider is authoritative, and how will the console validate its issuer, audience, signature, expiry, session revocation and step-up state server-side?
  2. Which approved role claims map to read, reply, audit, feature-flag, kill-switch, and knowledge-release permissions, and which approval/publish/rollback actions require maker-checker separation?
  3. Which audit fields, retention periods and incident procedures are required for each staff read and state-changing action?

### OQ-015 — Durable API and Conversation State
- **Blocks:** Production API and agent-runtime operation
- **Context:** Several API repositories, consent/preferences, knowledge snapshots, feedback, and event staging are process-local. No identity OTP flow is active. LangGraph currently uses `InMemorySaver`; migration and ORM declarations do not establish runtime persistence, RLS provisioning, checkpoint recovery, or NATS delivery. Production mode therefore returns 503 until these paths have approved implementations.
- **Specific Questions for SSRA ICT, SecOps & Operations:**
  1. Which database and schema own each mutable context, and what RLS/session variables bind every query to its verified subject, office, and role?
  2. What encryption, retention, deletion, backup, restore, and audit controls apply to each state class?
  3. Which checkpoint store and recovery semantics are approved, and what tests prove restart-safe single-thread and multi-replica continuation?
  4. Which transactional outbox/broker topology, retry policy, idempotency key, and dead-letter process are approved for domain events?

### OQ-016 — Appointment Inventory and Booking Authority
- **Blocks:** Phase 2 appointment self-service
- **Context:** The API previously returned fixed, expired sample slots and has no live office calendar or reservation provider. Listing or booking appointments must not imply a confirmed SSRA reservation without a source-of-truth response.
- **Specific Questions for SSRA Operations & ICT:**
  1. Which approved system owns office schedules, closures, slot capacity, and booking identifiers?
  2. What are the reservation expiry, cancellation, duplicate request, timezone, and conflict-resolution rules?
  3. What confirmation artifact may be shown to the taxpayer, and what is the staff escalation path when the provider is unavailable?

### OQ-017 — Document Scanning, OCR, and Evidence Guidance
- **Blocks:** Phase 2 document precheck and analysis
- **Context:** The prior deterministic document helpers and generated UI guidance have been removed because they could imply malware scanning, OCR, statutory calculations, or legal instructions without approved sources. HTTP handlers and the attachment inspection view fail closed until the relevant providers and provenance rules exist.
- **Specific Questions for SSRA ICT, SecOps & Legal:**
  1. Which malware scanning and OCR services are approved, and what evidence demonstrates coverage, versioning, and fail-safe behavior?
  2. What upload retention, deletion, encryption, size, and access-audit requirements apply?
  3. Which official knowledge snapshots and numeric tools may support document-derived statutory explanations, and who approves portal troubleshooting guidance?

### OQ-001 — e-Tax APIs, Schemas, Authentication & TIN Format
- **Blocks:** Phase 2 (Authenticated Self-Service)
- **Context:** SSRA's National e-Tax System (`etax.nra.gov.ss`) handles TIN registration, filing, payment, and Tax Compliance Certificates (TCC).
- **Specific Questions for SSRA ICT:**
  1. What are the exact REST/SOAP/GraphQL specifications for `verify_tin`, `get_registration_status`, `get_profile`, `get_filing_status`, `list_assessments`, `get_balance`, `list_payments`, and `get_tcc_status`?
  2. What is the canonical regex/checksum format for individual, business, and NGO TINs (including legacy NRA TINs)?
  3. How does e-Tax authenticate service-to-service calls (mTLS, OAuth2 client credentials, HMAC) and what rate limits apply?
  4. Is a non-production sandbox environment with synthetic taxpayers available?

### OQ-002 — e-Customs Platform & APIs
- **Blocks:** Phase 2
- **Context:** SSRA administers customs under the Customs Service Act 2013 and annual Financial Acts, converting foreign-currency values at the official Bank of South Sudan (BoSS) rate.
- **Specific Questions for SSRA Customs & ICT:**
  1. Which customs management system (e.g., ASYCUDA World or bespoke e-Customs portal) is currently deployed at NCA?
  2. Are APIs available for declaration status (`get_declaration_status`), tariff lookup (`lookup_tariff`), and official BoSS exchange rate feeds?

### OQ-003 — NCA Data-Centre Hosting Capacity & DR Topology
- **Blocks:** Phase 0 Gate Sign-off
- **Context:** All e-Tax, e-Customs, and SSRA Assist data and workloads are hosted in-country with the National Communication Authority (NCA).
- **Specific Questions for SSRA ICT & NCA:**
  1. What CPU, RAM, NVMe storage, and GPU models/VRAM are available in the primary NCA cluster for `vLLM`/`SGLang` and embedding/reranking servers?
  2. Is a secondary site/zone available in-country for Disaster Recovery (RPO ≤ 5 min, RTO ≤ 1 h)?
  3. What Linux host OS, NVIDIA Container Toolkit version, and S3-compatible storage endpoints (Ceph/MinIO) are standard in NCA's Docker Compose host environment?

### OQ-004 — Approved External AI Providers & Cross-Border Data Policy
- **Blocks:** Phase 1
- **Context:** Principle 7 requires full in-country execution on open-weight models by default, with external frontier providers optional behind `agentgateway`.
- **Specific Questions for SSRA Management & Legal:**
  1. Are any external frontier LLM providers (Anthropic, OpenAI, Google) approved for anonymous `T0` queries under Zero-Data-Retention (ZDR) agreements?
  2. What are each provider's availability and contractual terms for a South Sudan government authority?

### OQ-005 — Taxpayer & Staff Identity Proofing
- **Blocks:** Phase 2
- **Context:** `T1`–`T3` tools require verified identity (phone OTP bound to TIN, plus step-up OTP for `T3`). Staff require SSO + WebAuthn passkeys. The identity HTTP endpoint returns 503; test-only helpers cannot establish a production identity. Voice keypad step-up (`ssra_voice.verify_voice_dtmf_step_up`) needs an `OtpVerifier` from the approved provider and otherwise transfers the caller to an officer ([ADR-024](./adr/0024-voice-identity-step-up-and-carryover-fail-closed.md)).
- **Specific Questions for SSRA SecOps & ICT:**
  1. Which mobile network operators (Zain South Sudan, MTN South Sudan, Digitel) or aggregators provide OTP delivery and SIM-swap recency signals?
  2. Does SSRA operate an existing Active Directory / Entra ID / LDAP or Keycloak IdP for staff federation?
  3. What secondary knowledge factors from e-Tax are required when binding a phone number to a TIN for the first time?

### OQ-006 — Payment Channels, References & Bank of South Sudan Integration
- **Blocks:** Phase 2
- **Context:** A March 2026 directive routes all government revenue exclusively through the National e-Tax System into banks (cash-free collection).
- **Specific Questions for SSRA Finance & ICT:**
  1. Does e-Tax expose an API to generate a payment assessment/reference number (`generate_payment_reference`) and should SSRA Assist expose it at Tier `T3`?
  2. Which commercial banks and mobile-money operators are currently integrated with e-Tax and the Treasury Single Account (TSA)?
  3. How is the official Bank of South Sudan (BoSS) exchange rate published and consumed electronically?

### OQ-007 — Official Telecom Channels & Aggregator Agreements
- **Blocks:** Phase 1
- **Context:** Phase 1 launches on Web PWA, WhatsApp Business Platform, and SMS FAQ; Phase 4 adds USSD and Voice/IVR.
- **Specific Questions for SSRA Communications & ICT:**
  1. What is SSRA's verified Meta WhatsApp Business Account (WABA) phone number and BSP/direct integration status?
  2. What are the registered SMS Sender IDs, USSD short codes, and toll-free IVR numbers across MNOs?

### OQ-008 — Language Priorities, Termbase Ownership & Review Capacity
- **Blocks:** Phase 1
- **Context:** Phase 1 supports English (`en`), Juba Arabic (`pga`, often written in Latin script), and Arabic (`ar`, RTL); Phase 4 targets Dinka (`din`), Nuer (`nus`), Bari (`bfa`), Zande (`zne`), and Shilluk (`shk`).
- **Specific Questions for SSRA Communications & Legal:**
  1. Who in SSRA Legal/Communications owns final approval of the multilingual tax termbase (`ai/termbase/`) and the 600+ Phase 1 golden eval items (300 `en`, 150 `ar`, 150 `pga`)?
  2. What orthographic convention should be used as primary for Juba Arabic (`pga`) in text channels (Latin script vs. Arabic script variants)?
  3. Who reviews the public web interface strings? As of 2026-10-23 (AUD-020), the web shell shows interface text only for `en`, `pga`, and `ar`; the five Phase 4 locales show English with a notice. The current Latin-script `pga` landing subtitle contains one Arabic-script word (`الموظفين`); a qualified reviewer should correct it rather than an engineer.
  4. Who approves voice launch evidence? As of 2026-10-24 (AUD-037), `ssra_voice.APPROVED_VOICE_WER_EVIDENCE` is empty, so no language runs on voice and callers are transferred to an officer. Each entry needs a measured WER on a named SSRA test set, its date, and its utterance count.

### OQ-009 — Legal Retention, Taxpayer Secrecy & Fiscal Calendar Confirmation
- **Blocks:** Phase 1
- **Context:** Constitution Article 22, NRA Act 2016 (as amended 2023), Taxation Act 2009, Cybercrimes Provisional Order 2021, and the planned 2026 Data Protection Bill govern privacy and secrecy.
- **Specific Questions for SSRA Legal:**
  1. Confirm the statutory retention periods for conversation logs, voice recordings, case attachments, and `AuditEvent` WORM archives. Until then, `ssra_voice.VoiceRetentionPolicy` has no periods (keep nothing after the call) and refuses to store raw audio (AUD-039).
  2. Confirm the exact statutory wording required for AI transparency disclosure and voice recording consent. Until then, the public web composer shows interim English wording (AUD-021): "SSRA Assist is an automated AI assistant and can make mistakes. Check answers against the cited sources. Don’t enter your TIN, phone number, or passwords in this public chat."
  3. Confirm the fiscal year dates (1 July to 30 June) and statutory filing/payment deadlines per tax type for the initial `TaxFact` seed registry.

### OQ-010 — Contact-Centre Operations, Queues, Hours & SLAs
- **Blocks:** Phase 1
- **Context:** Principle 6 guarantees one-step human escalation during office hours and callback booking outside office hours.
- **Specific Questions for SSRA Contact Centre:**
  1. What are the official contact-centre operating hours in `Africa/Juba` (`UTC+02:00`) and public holiday calendar?
  2. What specialist queues (e.g., Domestic Tax, Large Taxpayers, SME/PAYE, Customs, Technical e-Tax Support, Scam/Compliance) and SLA targets apply to `Handoff` and `Case` entities?

### OQ-011 — Anti-Impersonation Official-Channel Registry
- **Blocks:** Phase 1
- **Context:** Fake collectors and impersonation scams are active risks; `official-channels` tools allow taxpayers to verify any account, phone number, sender ID, or link.
- **Specific Questions for SSRA Communications & SecOps:**
  1. Provide the authoritative list of official SSRA domains, social media handles, phone numbers, SMS sender IDs, WhatsApp numbers, and designated bank collection paths to publish in the signed registry.
  2. Where should `report_scam` (`T2`) route alerts inside SSRA Compliance/SecOps?

### OQ-012 — Procurement, Open-Source Licensing & Sanctions/Export Compliance
- **Blocks:** Phase 0 Gate Sign-off
- **Context:** Section 1 requires stopping before adding any dependency with licensing or export-control implications.
- **Specific Questions for SSRA Procurement & Legal:**
  1. Confirm SSRA's open-source software policy (e.g., acceptance of Apache-2.0, MIT, BSD-3-Clause, MPL-2.0, and whether AGPLv3/SSPL components are permitted or prohibited for self-hosted internal tooling).
  2. Confirm vendor screening and export-control compliance requirements for NCA-hosted software and container base images.
