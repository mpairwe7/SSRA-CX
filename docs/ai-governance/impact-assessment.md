# SSRA Assist — AI Impact Assessment & Privacy Impact Assessment (`docs/ai-governance/impact-assessment.md`)

**Status:** v1.1 (Governance requirements; not operational-readiness evidence)

**Date:** 2026-10-21
**Standards:** ISO/IEC 42001:2023, NIST AI RMF 1.0 (AI 600-1), South Sudan Constitution Art. 22, AU Malabo Convention  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 2, 4, 12.1, 12.5, 18

---

## 1. Purpose & Public-Interest Justification

SSRA Assist improves voluntary tax compliance and taxpayer trust across South Sudan by providing instant, cited, multilingual guidance (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`) over low-bandwidth channels (Web PWA, WhatsApp, SMS, USSD, Voice/IVR), helping citizens and businesses avoid queues and verify official cash-free bank remittance channels (`https://etax.nra.gov.ss/`).

This assessment records the safeguards required for a future service; it does not certify that integrations are live or phases have passed their exit gates. The current API and agent runtime fail closed outside explicit reference mode, and identity, document analysis, appointments, staff operation, and production analytics remain unavailable pending their approvals and implementations (ADR-019; OQ-005, OQ-013–OQ-017).

---

## 2. Fundamental Rights, Fairness & Inclusivity Impact

| Impact Dimension | Identified Risk | Mandatory Technical & Operational Safeguard |
|---|---|---|
| **Right to Privacy (Constitution Art. 22)** | Exposure of taxpayer TIN, filings, or balance | Out-of-band OTP+TIN identity proofing; OAuth 2.1 RFC 8693 `subject_ref` token exchange; OpenBao Transit AES-GCM column encryption; Presidio PII redaction; `DELETE /v1/consent/preferences/{subject_ref}` right-to-erasure. |
| **Financial & Legal Harm** | Taxpayer relies on an invented rate or deadline | 100% deterministic `TaxFact` registry (`libs/ssra_rules`); `numeric_provenance` output validator blocks any untraced number; calculators badged `ESTIMATE ONLY`. |
| **Administrative Due Process** | Automated denial of a waiver, refund, or dispute | Tier `T4` has **zero MCP tools** and routes deterministically to human SSRA officers (`ai/policies/risk-tiers.yaml`). |
| **Linguistic & Digital Inclusion** | Exclusion of non-English speakers or 2G/feature-phone users | First-class SMS (GSM-7 / UCS-2) and USSD (`<= 182` chars, zero LLM latency) channels; 2G Low-Data Text Mode; ≤ 5-point language parity gate in `evals/`. |
| **Fraud & Impersonation Protection** | Fake collectors demanding cash or mobile-money transfers | Signed `official-channels` registry; March 2026 cash-free bank-only notice in every payment response and outbound template footer. |
| **Data Sovereignty** | Taxpayer data processed outside South Sudan | In-country NCA hosting on open-weight models (`vLLM`/`SGLang`); external providers disabled by default until SSRA approves `OQ-004`. |
