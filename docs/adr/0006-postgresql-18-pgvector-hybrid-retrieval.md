# ADR-006: PostgreSQL 18 + pgvector 0.8+ Hybrid Retrieval Store

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Medium
- **Linked Open Questions:** `OQ-003`, `OQ-008`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 5, 7, 17, Appendix A

---

## 1. Problem Statement

How do we store operational state, LangGraph conversation checkpoints, hash-chained audit logs, and multilingual legal knowledge embeddings in one sovereign database before introducing dedicated external search engines?

## 2. Context

SSRA Assist requires:
- ACID relational storage for the 10 core entities (`Conversation`, `Message`, `ToolInvocation`, `Confirmation`, `Handoff`, `Case`, `Consent`, `KnowledgeSnapshot`, `TaxFact`, `AuditEvent`);
- Durable LangGraph thread checkpointing;
- Hybrid lexical + semantic retrieval over South Sudan tax and customs legislation (Acts, Financial Acts, circulars, FAQs, procedures) filtered by `KnowledgeSnapshot` version, `effective_from`/`effective_to` dates, language (`en`, `pga`, `ar`), and audience.

Running a separate distributed vector database (e.g., Milvus/Qdrant) and an OpenSearch cluster from day one increases memory footprint, backup complexity, and split-brain synchronization risks on NCA infrastructure (`OQ-003`). PostgreSQL 18 provides native `uuidv7()`, improved partition pruning, and `pgvector` 0.8+ provides HNSW indexes with **iterative index scans**, ensuring filtered vector queries (`WHERE snapshot_version = ... AND language = ...`) never return fewer than `k` results due to post-filtering.

## 3. Options Considered

1. **PostgreSQL 18 + Separate Dedicated Vector DB + OpenSearch from Day 1:** Three stateful clusters to operate, back up, and secure with mTLS/encryption; transactional out-of-sync risk when publishing or rolling back a `KnowledgeSnapshot`.
2. **PostgreSQL 18 + `pgvector` 0.8+ Hybrid Search (FTS + HNSW Iterative Scans) + Multilingual Reranker (Selected):** Single CloudNativePG HA cluster with point-in-time recovery (PITR) for relational entities, checkpoints, and hybrid retrieval; add OpenSearch only if Arabic (`ar`) or Juba Arabic (`pga`) recall@k fails Phase 1 evaluation gates.

## 4. Decision

We adopt Option 2:

1. **Primary Data & Retrieval Engine:** PostgreSQL 18.x managed via CloudNativePG with `pgvector` 0.8+ enabled.
2. **Hybrid Retrieval (`services/agent-runtime/src/ssra_runtime/retrieval/` & `mcp-servers/knowledge`):**
   - Combine PostgreSQL full-text search (`tsvector` + trigram `pg_trgm` for code-switched Juba Arabic and NRA/SSRA synonym expansion) with `pgvector` HNSW cosine similarity (`SET hnsw.iterative_scan = relaxed_order`).
   - Fuse lexical and dense scores via Reciprocal Rank Fusion (RRF), then pass top candidates to the sovereign multilingual reranker (`BGE-M3` or `Qwen3-Reranker`, selected via bake-off on SSRA eval datasets).
   - Enforce mandatory metadata filters on every query: `snapshot_version = current_published_snapshot`, `approval_state = 'PUBLISHED'`, and `effective_from <= as_of_date <= COALESCE(effective_to, 'infinity')`.
3. **Conditional OpenSearch Trigger:** If Phase 1 evaluation shows Arabic (`ar`) or Juba Arabic (`pga`) `recall@5` trailing English by more than the 5-point parity gate (Section 14.2) due to morphological tokenization, we will introduce an OpenSearch index behind the same `KnowledgePort` interface without changing callers.

## 5. Consequences

- **Positive:** Atomic one-step knowledge snapshot activation and rollback (`KnowledgeSnapshot`), single Velero + WAL archiving pipeline (RPO ≤ 5 min, RTO ≤ 1 h), and lower hardware footprint at NCA.
- **Negative / Trade-offs:** PostgreSQL native Arabic stemming is simpler than specialized ICU/Morphological analyzers in OpenSearch, mitigated by hybrid dense + trigram retrieval and neural reranking.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. All retrieval calls pass through `mcp-servers/knowledge` and a clean `KnowledgeRetrievalPort`, allowing dual-read/dual-write migration to OpenSearch if triggered by eval metrics.
