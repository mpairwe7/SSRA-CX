# SSRA Assist — Personas, Core Journeys & Conversation Design (`docs/product/README.md`)

**Status:** Draft v1 (Phase 0)  
**Date:** 2026-10-16  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 2, 3, 7, 11

---

## 1. User Personas

1. **Amina — Salaried Employee (Juba, PAYE Taxpayer):** Uses an entry-level Android phone on prepaid data; speaks English (`en`) and Juba Arabic (`pga`). Wants to check how PAYE is calculated on her salary and confirm whether an SMS claiming she owes tax is genuinely from SSRA.
2. **Deng — Sole Proprietor & SME Trader (Wau / Juba):** Uses WhatsApp and SMS; often experiences intermittent 2G connectivity. Needs step-by-step guidance to register for a TIN on `etax.nra.gov.ss` (after Ministry of Justice business validation), file monthly returns, and pay through designated banks (never cash collectors).
3. **Mary — NGO Finance Officer (Juba):** Manages payroll and withholding tax compliance for an INGO registered with the Ministry of Humanitarian Services; needs accurate statutory deadlines (`Africa/Juba`), withholding rate citations, and Tax Compliance Certificate (TCC) status checks.
4. **Hassan — Importer & Clearing Agent (Nimule / Port Corridor):** Communicates in Arabic (`ar`, RTL) and English (`en`); needs customs procedures, tariff lookups, and declaration status checks converted only at official Bank of South Sudan (BoSS) rates.
5. **Grace — SSRA Contact-Centre Agent & Supervisor (Juba HQ):** Uses `apps/console` with a WebAuthn passkey; handles `T4` escalations (waivers, disputes, complex cases), reviews AI-drafted cited replies, and tracks SLA timers.

---

## 2. Phase 1 Core Guided Journeys (`T0` & `T2`)

1. **Get a TIN (`guided_journey: tin_registration`):**
   - Branches by applicant type: **Citizen/Individual**, **Business** (requires Ministry of Justice eServices validation first), or **NGO** (requires Ministry of Humanitarian Services registration number + active phone number).
   - Directs applicant to official portal `https://etax.nra.gov.ss/` and lists exact required documents.
2. **File a Return & Pay via Official Bank Channels (`guided_journey: file_and_pay`):**
   - Explains e-Tax electronic filing and reinforces the **March 2026 cash-free directive**: all government revenue is paid exclusively through the National e-Tax System into designated banks—never to individual collectors.
3. **Obtain a Tax Compliance Certificate (`guided_journey: obtain_tcc`):**
   - Explains that TCCs are issued exclusively via e-Tax (`etax.nra.gov.ss`) and outlines eligibility requirements.
4. **Deterministic PAYE & Withholding Estimator (`calculator`):**
   - Collects gross monthly income / payment category, invokes `mcp-servers/tax-facts`, and displays a cited breakdown clearly badged as an **Informational Estimate Only**.
5. **"Is This Really SSRA?" Anti-Scam Verifier (`verify_official`):**
   - Checks any phone number, SMS sender ID, WhatsApp number, website URL, or bank account against `mcp-servers/official-channels` and offers 1-click `report_scam` (`T2` with confirmation).
6. **One-Step Human Handoff & Complaint Intake (`handoff` / `complaint_intake`):**
   - Connects to a live SSRA agent during `Africa/Juba` office hours or schedules a callback / logs a minimal-data case outside office hours.
