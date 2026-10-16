# SSRA Assist — Open Questions Register (`docs/open-questions.md`)

**Last Updated:** 2026-10-16  
**Governance Rule:** Never invent South Sudan tax law, rates, deadlines, penalties, fees, exchange rates, endpoints, or data formats. Whenever an upstream capability, legal rule, or operational parameter is unconfirmed by SSRA, log it here as `OQ-###`, define a clean port interface, build a synthetic mock adapter, and enforce the safest runtime fallback (abstain and offer human handoff).

---

## Summary Table

| ID | Question | Blocks | Owner (SSRA) | Status | Safe Fallback Until Answered |
|---|---|---|---|---|---|
| **OQ-001** | **e-Tax APIs:** endpoints, auth model, rate limits, sandbox, data dictionary, TIN format | Phase 2 | SSRA ICT & Domestic Tax | 🔴 Open | Define `ETaxPort` in `libs/ssra_adapters`; use deterministic mock adapter with synthetic data (`TIN ••••1234`); disable live T1/T3 e-Tax calls. |
| **OQ-002** | **e-Customs platform and APIs:** declaration status, tariff data, HS code schedule | Phase 2 | SSRA Customs & ICT | 🔴 Open | Define `ECustomsPort`; mock adapter returns synthetic test declarations; public assistant answers only published general customs procedures (T0) and hands off specific declaration/tariff queries. |
| **OQ-003** | **Hosting:** NCA data-centre capacity (CPU, GPU, storage, network), DR site, any approved regional cloud | Phase 0 (Sign-off) | SSRA ICT & NCA | 🔴 Open | Develop and test against portable Docker Compose (`task up`) and vendor-neutral Kubernetes (RKE2/k3s) Helm/OpenTofu manifests sized for modular CPU + single/dual GPU profiles. |
| **OQ-004** | **AI providers:** approved external models, data classes allowed to leave the country, zero-retention contracts | Phase 1 | SSRA Management, Legal & SecOps | 🔴 Open | Default all model routing in `ai/routing/` to in-country self-hosted open-weight models (`vLLM`/`SGLang`); keep external provider plug-ins disabled by default behind `agentgateway`. |
| **OQ-005** | **Identity:** civil-registry or national-ID verification, OTP delivery partners, SIM-swap signals, staff identity provider | Phase 2 | SSRA ICT, SecOps & Telcos | 🔴 Open | Use local Keycloak realm with mock OTP/SIM-swap provider in dev/staging; block production T1+ rollout until identity proofing is approved by SSRA SecOps. |
| **OQ-006** | **Payments:** who may generate payment references, bank and mobile-money partners, Bank of South Sudan integration | Phase 2 | SSRA Finance, BoSS & ICT | 🔴 Open | Provide static, cited instructions for official e-Tax bank remittance only; keep `generate_payment_reference` feature-flagged off (`*` in catalog); never compute FX rates. |
| **OQ-007** | **Channels:** WhatsApp number and verification, SMS sender ID, USSD short code, toll-free voice line, operator agreements | Phase 1 | SSRA Communications & ICT | 🔴 Open | Build against `ChannelPort` with local webhook/SMPP/USSD simulators in `infra/compose/`; populate placeholder sender IDs clearly marked `UNVERIFIED_DEV_ONLY`. |
| **OQ-008** | **Languages:** priority order, translation and review capacity, termbase ownership | Phase 1 | SSRA Communications & Legal | 🔴 Open | Scaffold ICU message catalogs and `ai/termbase/` for `en`, `pga`, and `ar` (RTL) for Phase 1, plus `din`, `nus`, `bfa`, `zne`, `shk` placeholders; require human review sign-off before publishing Tier B/C translations. |
| **OQ-009** | **Legal:** retention schedule, recording consent, taxpayer-secrecy provisions, data-protection bill status, fiscal year confirmation (1 July – 30 June) | Phase 1 | SSRA Legal | 🔴 Open | Enforce GDPR-grade / AU Malabo Convention defaults, strict PII redaction (Presidio), explicit opt-in consent, short default checkpoint TTLs, and require SSRA Legal approval on every `KnowledgeSnapshot` and `TaxFact`. |
| **OQ-010** | **Operations:** contact-centre size and hours, escalation matrix, SLAs, console roles | Phase 1 | SSRA Contact Centre & Operations | 🔴 Open | Configure parameterised office hours (`Africa/Juba`), queues, RBAC roles, and SLA timers in `services/api` and Temporal with conservative defaults; route out-of-hours escalations to callback intake. |
| **OQ-011** | **Official-channel registry and branding** for anti-scam verification | Phase 1 | SSRA Communications & SecOps | 🔴 Open | Seed `official-channels` MCP server with verified domain `etax.nra.gov.ss` and March 2026 cash-free bank-only directive; mark phone/short-code/bank account entries as pending SSRA sign-off. |
| **OQ-012** | **Procurement:** open-source policy, licensing, export-control and sanctions screening of vendors | Phase 0 (Sign-off) | SSRA Procurement & Legal | 🔴 Open | Restrict Phase 0 stack strictly to permissive/open OSI-approved self-hostable software (Apache-2.0, MIT, BSD, PostgreSQL); generate CycloneDX SBOMs for license audit. |

---

## Detailed Question Records

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
  3. What Kubernetes distribution (RKE2 vs. k3s) and storage classes (Ceph/Longhorn/MinIO) are standard in NCA's environment?

### OQ-004 — Approved External AI Providers & Cross-Border Data Policy
- **Blocks:** Phase 1
- **Context:** Principle 7 requires full in-country execution on open-weight models by default, with external frontier providers optional behind `agentgateway`.
- **Specific Questions for SSRA Management & Legal:**
  1. Are any external frontier LLM providers (Anthropic, OpenAI, Google) approved for anonymous `T0` queries under Zero-Data-Retention (ZDR) agreements?
  2. What are each provider's availability and contractual terms for a South Sudan government authority?

### OQ-005 — Taxpayer & Staff Identity Proofing
- **Blocks:** Phase 2
- **Context:** `T1`–`T3` tools require verified identity (phone OTP bound to TIN, plus step-up OTP for `T3`). Staff require SSO + WebAuthn passkeys.
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

### OQ-009 — Legal Retention, Taxpayer Secrecy & Fiscal Calendar Confirmation
- **Blocks:** Phase 1
- **Context:** Constitution Article 22, NRA Act 2016 (as amended 2023), Taxation Act 2009, Cybercrimes Provisional Order 2021, and the planned 2026 Data Protection Bill govern privacy and secrecy.
- **Specific Questions for SSRA Legal:**
  1. Confirm the statutory retention periods for conversation logs, voice recordings, case attachments, and `AuditEvent` WORM archives.
  2. Confirm the exact statutory wording required for AI transparency disclosure and voice recording consent.
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
