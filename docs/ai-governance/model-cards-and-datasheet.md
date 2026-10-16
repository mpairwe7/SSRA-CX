# SSRA Assist — Model Cards & Knowledge Corpus Datasheet (`docs/ai-governance/model-cards-and-datasheet.md`)

**Status:** v1.0 (Phase 0–4 Governance Deliverable)  
**Date:** 2026-10-16  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 6.4, 7, 11, 12.5

---

## 1. Sovereign Model Cards

### 1.1 Model Card 1: Fast Guard & Intent Router (`ssra-sovereign/qwen2.5-7b-instruct`)
- **Role in Graph:** Nodes 3 (`input_guard`) and 4 (`understand`).
- **Hosting:** In-country NCA Kubernetes GPU pool via vLLM/SGLang (`ADR-007`).
- **Inputs & Outputs:** Receives Presidio-redacted user input; emits strictly validated `Intent` JSON Schema (`intent`, `slots`, `language`, `confidence`).
- **Safety Constraint:** Never assigns risk tiers; risk tiers are resolved deterministically from `ai/policies/risk-tiers.yaml`.
- **Target Latency:** p95 ≤ 300 ms.

### 1.2 Model Card 2: Multilingual Grounded Composer (`ssra-sovereign/qwen2.5-14b-instruct`)
- **Role in Graph:** Node 8 (`compose`).
- **Hosting:** In-country NCA GPU pool (secondary fallback: `ssra-sovereign/llama-3.3-8b-instruct`; CPU emergency fallback: `ssra-sovereign/qwen2.5-3b-cpu-gguf`).
- **Inputs & Outputs:** Receives layered prompt `L0`–`L5` with spotlighted data-only delimiters (`<untrusted_retrieved_evidence>`, `<untrusted_tool_artifacts>`) and `ai/termbase/glossary.yaml`; emits structured `Answer` (`segments[]`, `citations[]`, `numbers[]`, `ui_component`).
- **Safety Constraint:** Every output passes Node 9 (`output_guard`: `numeric_provenance` 100% gate, `grounding`, `pii`, `neutrality`) before reaching any user.

### 1.3 Model Card 3: Multilingual Embedding & Reranker (`BGE-M3` / `Qwen3-Embedding` + `Qwen3-Reranker`)
- **Role:** Hybrid lexical + dense vector retrieval (`pgvector` 0.8+ HNSW iterative scans) and cross-encoder reranking across English (`en`), Arabic (`ar`), Juba Arabic (`pga`), and Tier C national languages (`din`, `nus`, `bfa`, `zne`, `shk`).

### 1.4 Model Card 4: Speech Pipeline (`Whisper-large-v3-turbo` & `Meta Omnilingual ASR`)
- **Role:** Phase 4 Voice/IVR (`services/voice`).
- **Launch Gate:** A language is enabled on Voice/IVR only when its measured Word Error Rate (WER) on SSRA test sets is `<= 0.12` (`MAX_VOICE_WER_GATE`). Exceeding the gate triggers an immediate warm transfer to an SSRA officer.

---

## 2. Datasheet for the SSRA Knowledge Corpus (`knowledge/`)

1. **Motivation:** Provide an authoritative, auditable, versioned legal and procedural corpus for SSRA Assist so that zero unverified claims or numbers ever reach taxpayers.
2. **Composition:** Public statutory instruments enacted by the Republic of South Sudan and circulars issued by SSRA:
   - South Sudan Revenue Authority Act, 2016 (as amended October 2023)
   - Taxation Act, 2009 (as amended)
   - Customs Service Act, 2013
   - Financial Act 2024/2025 & SSRA Implementation Circulars
   - March 2026 Cash-Free Bank Remittance Directive
   - Official e-Tax Portal (`https://etax.nra.gov.ss/`) Registration, Filing & TCC Procedures
3. **Collection & Ingestion Process:** Parsed by legal hierarchy (`Part`, `Chapter`, `Section`, `Subsection`), assigned immutable `section_anchor` IDs and SHA-256 checksums, and aligned with the multilingual tax termbase (`ai/termbase/glossary.yaml`).
4. **Release & Maintenance:** Governed by the 6-step Knowledge Release workflow in `services/api` (`knowledge_admin`) and `apps/console` (`DRAFT` → `LEGAL_REVIEW` → `APPROVED` → `PUBLISHED` → `EVAL_GATE` → `1_STEP_ROLLBACK`).
5. **Privacy & Confidentiality:** Contains `PUBLIC` statutory and procedural guidance only; zero taxpayer records or confidential drafts are stored in the corpus (`knowledge/sources.yaml`).
