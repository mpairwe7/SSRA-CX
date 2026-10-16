# ADR-009: Deterministic Tax Facts Registry and Numeric Provenance Guard

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Legal, SSRA Domestic Tax & Customs
- **Reversal Cost:** High
- **Linked Open Questions:** `OQ-006`, `OQ-009`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 1, 2, 4, 6.1, 6.2, 7, 14.2, 17

---

## 1. Problem Statement

How do we achieve the mandatory **100% numeric accuracy launch gate** on South Sudan tax rates, thresholds, deadlines, penalties, fees, and PAYE/withholding estimates with zero fabricated or outdated numbers?

## 2. Context

South Sudan tax rates and fees are set by the NRA Act 2016 (as amended 2023), the Taxation Act 2009 (as amended), the Customs Service Act 2013, and annual Financial Acts (such as the Financial Act 2024/2025 effective via SSRA circular). Foreign-currency customs values convert to SSP at the official Bank of South Sudan (BoSS) rate. Allowing an LLM to recall tax brackets from pre-training weights or parse numbers loosely from unstructured paragraphs risks stating an outdated rate or miscalculating a PAYE estimate—which has legal and financial consequences for taxpayers and SSRA.

## 3. Options Considered

1. **RAG-Only over PDF/Markdown Tax Guides:** LLMs frequently misread table rows, confuse effective years, or make arithmetic errors when computing progressive tax brackets. Fails the 100% numeric accuracy gate.
2. **Versioned Structured `TaxFact` Registry + Deterministic `ssra_rules` Engine + Mandatory `numeric_provenance` Output Validator (Selected):** Separates legal numbers and calculations into deterministic code/data exposed via MCP (`mcp-servers/tax-facts`) and blocks any LLM output containing an unverified number.

## 4. Decision

We adopt Option 2:

1. **Structured `TaxFact` Registry (`knowledge/tax-facts/` & PostgreSQL `tax_facts` table):**
   - Every rate, bracket threshold, statutory deadline rule, penalty rate, and official fee is stored as a typed `TaxFact` record with `key`, `value`, `unit`, `currency` (`SSP` or `USD`), `applies_to`, `effective_from`, `effective_to`, `legal_ref` (Act/Financial Act/Circular + Section), `approved_by`, and `version`.
   - Unconfirmed rates or rules are never guessed; they are logged in `docs/open-questions.md` and excluded until SSRA Legal signs off.
2. **Deterministic Rules & Calculator Library (`libs/ssra_rules` & `mcp-servers/tax-facts`):**
   - `calculate_paye_estimate` and `calculate_withholding_estimate` execute pure, deterministic Python functions using `Decimal` arithmetic (`ROUND_HALF_UP`) and `Africa/Juba` (`UTC+02:00`) date logic against active `TaxFact` rows.
   - Tested with **Hypothesis property-based tests** and **`mutmut` mutation testing** in CI.
   - Every calculator output carries an explicit disclaimer field (`is_estimate: true`, *"This is an informational estimate based on published SSRA rates, not an official assessment"*).
   - The assistant **never** computes or guesses foreign-currency exchange rates (Principle 2 & Section 2).
3. **Structured `Answer` Numbers & `numeric_provenance` Output Guard (`services/agent-runtime/src/ssra_runtime/guardrails/numeric_provenance.py`):**
   - The `compose` node returns a structured `Answer` whose `numbers[]` array lists every number (`value`, `unit`, `source_ref` pointing to an MCP `Artifact` ID or `TaxFact` key).
   - The `numeric_provenance` guard extracts all numerals/amounts/percentages/dates from `Answer.segments[]` (across English, Arabic numerals, and Eastern Arabic numerals `٠-٩`) and verifies that 100% of them match `Answer.numbers[]` and the underlying tool artifact from the current turn.
   - Any mismatch triggers a single regeneration with validator feedback; if it still fails, the runtime suppresses the generated text and returns a safe abstention + handoff offer.

## 5. Consequences

- **Positive:** Mathematically guarantees 0% hallucinated tax calculations and enforces traceable legal citations for every figure shown to a taxpayer.
- **Negative / Trade-offs:** Whenever Parliament enacts a new annual Financial Act or SSRA issues a rate circular, SSRA Legal/Policy must publish an updated `TaxFact` snapshot through the Console Knowledge Release workflow before the assistant will state the new figures.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** High (core safety invariant of the platform). The `TaxFact` YAML/JSON schema is portable across relational databases and rules engines.
