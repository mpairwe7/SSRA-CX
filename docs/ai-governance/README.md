# SSRA Assist — AI Governance: Risk Register, System Card & Impact Assessment (`docs/ai-governance/README.md`)

**Status:** Draft v1 (Phase 0)  
**Date:** 2026-10-16  
**Standards Alignment:** NIST AI RMF 1.0 + Generative AI Profile (NIST AI 600-1), ISO/IEC 42001:2023, AU Malabo Convention, South Sudan Constitution Art. 22  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 4, 6.4, 7, 12.5, 14

---

## 1. System Card — SSRA Assist

### 1.1 Intended Use
- **System Name:** SSRA Assist (South Sudan Revenue Authority Virtual Assistant & Staff Copilot)
- **Primary Purpose:** Provide grounded, cited public tax and customs information (`T0`), deterministic tax estimates (`T0`), official payment/channel anti-scam verification (`T0`/`T2`), authenticated taxpayer self-service reads (`T1`) and confirmed low-risk writes (`T2`/`T3`), and staff inbox assistance (`Phase 3`).
- **Intended Users:** Taxpayers in South Sudan and the diaspora (`en`, `pga`, `ar`, and Phase 4 national languages `din`, `nus`, `bfa`, `zne`, `shk`) and SSRA Contact-Centre, Domestic Tax, Customs, Legal, QA, and SecOps staff.

### 1.2 Out-of-Scope & Prohibited Uses (Hard Non-Goals)
- **Never** executes payments, refunds, or bank/mobile-money transfers.
- **Never** grants waivers, penalty remissions, or tax assessment changes (`T4` — human-only).
- **Never** issues binding legal rulings or advice beyond published SSRA guidance.
- **Never** computes or guesses foreign-currency exchange rates (only official Bank of South Sudan rates via deterministic tools).
- **Never** comments on political figures, parties, disputes, or security events.
- **Never** trains foundation models on taxpayer conversation data without written SSRA approval.

### 1.3 Transparency & Human Oversight
- Every conversation starts with an explicit disclosure in the user's language that they are interacting with **SSRA's automated virtual assistant**.
- Users can escalate to a human agent (`AGENT` keyword or UI button) in a single step during office hours (`Africa/Juba`) or request a callback outside office hours.
- Staff in `apps/console` inspect the exact prompt version, `KnowledgeSnapshot` version, retrieved citations, and tool artifacts for any conversation.
- Auditors (`ssra_auditor` / `qa`) operate under strict read-only Separation of Duties (`executeConsoleProxy` blocks operational mutations), inspect turn-by-turn forensic conversation replays (`/admin/replay`, `buildForensicReplayTimelineView`), score sampled turns against the 4-dimension QA rubric (`evaluateAuditorQaRubricSubmission`), monitor language parity gaps (`buildAuditorDriftAndFairnessView`), and export ISO/IEC 42001 / EU AI Act Art. 12 evidence bundles (`buildAuditorEvidencePackage`) gated on an intact WORM hash chain (`buildAuditorTrailIntegrityView`).

---

## 2. AI Risk Register

| Risk ID | Risk Category (NIST AI 600-1) | Description | Likelihood (Pre-Control) | Impact | Deterministic Mitigation | Residual Risk | Owner |
|---|---|---|---|---|---|---|---|
| **AIR-001** | Confabulation / Numeric Hallucination | Assistant states an invented tax rate, threshold, deadline, or PAYE figure | High | Critical | Numbers come exclusively from `mcp-servers/tax-facts` or `ledger`; `numeric_provenance` guard blocks any unverified numeral (100% gate). | Low | Principal Architect & SSRA Legal |
| **AIR-002** | Data Privacy & Cross-Taxpayer Leakage | Assistant leaks TIN or balance of Taxpayer A to Taxpayer B | Medium | Critical | Out-of-band OTP+TIN proofing; OAuth 2.1 RFC 8693 `subject_ref` token exchange; Presidio PII redaction; 0-case red-team gate. | Very Low | SSRA SecOps |
| **AIR-003** | Indirect Prompt Injection & Goal Hijack | Malicious text in uploaded document or retrieved chunk hijacks tool execution | High | High | `L0`–`L5` spotlighting delimiters; `input_guard` classifier; OPA `policy_gate`; single-use `confirmation_token` bound to `args_hash`. | Low | SSRA SecOps |
| **AIR-004** | Multilingual Disparity (`en` vs. `ar` / `pga`) | Lower retrieval recall or mistranslated tax terms in Arabic or Juba Arabic | Medium | High | Enforced `ai/termbase/` glossary; hybrid FTS + `pgvector` HNSW + multilingual reranker; ≤ 5-point parity gate in `evals/`. | Low | SSRA Communications & Legal |
| **AIR-005** | Impersonation & Payment Diversion | Scammers impersonate SSRA collectors or assistant outputs unverified payment details | High | Critical | `official-channels` MCP registry; March 2026 bank-only cash-free notice attached to payment guidance; closed UI component registry. | Low | SSRA Communications & SecOps |
| **AIR-006** | Unauthorized Consequential Action | Assistant books/cancels or requests TCC without explicit taxpayer intent | Medium | High | LangGraph `interrupt()` in `confirm` node + cryptographic single-use `confirmation_token` + `idempotency_key`. | Very Low | Principal Architect |

---

## 3. Model Cards & Knowledge Corpus Datasheet Summary

- **Baseline Sovereign Models (`ai/routing/model-routing.yaml`):**
  - **Guard / Router (`understand`, `input_guard`):** Open-weight instruction model (Qwen / Llama / Gemma small tier) served via vLLM/SGLang in-country at NCA.
  - **Composer (`compose`):** Open-weight multilingual instruction model validated on SSRA `en`, `pga`, and `ar` golden sets.
  - **Embeddings & Reranker:** Multilingual dense embedding + cross-encoder reranker (`BGE-M3` / `Qwen3-Embedding` + `Qwen3-Reranker`).
- **Knowledge Corpus Datasheet (`knowledge/sources.yaml`):**
  - Contains only public, SSRA Legal-approved statutory instruments (NRA Act 2016 as amended 2023, Taxation Act 2009, Customs Service Act 2013, Financial Act 2024/2025 circulars, official e-Tax procedures, and office directory).
  - Every chunk carries `doc_type`, `issuer`, `gazette_or_circular_ref`, `effective_from`, `effective_to`, `language`, `approval_state`, and `checksum`.
