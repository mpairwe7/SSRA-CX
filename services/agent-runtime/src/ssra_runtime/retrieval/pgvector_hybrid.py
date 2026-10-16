"""PostgreSQL 18 + pgvector 0.8+ Hybrid RRF Search & Multilingual Embedding/Reranker Bake-Off (Section 7 & ADR-006).

Implements:
1. `build_pgvector_hybrid_rrf_sql`: Generates the parameterized PostgreSQL 18 + pgvector 0.8+
   hybrid query combining `ts_rank_cd` full-text search and HNSW cosine distance (`<=>`) under
   `SET LOCAL hnsw.iterative_scan = 'relaxed_order'`.
2. `reciprocal_rank_fusion`: Fuses lexical and dense candidate rankings (`k = 60`).
3. `evaluate_embedding_reranker_bakeoff`: Computes `recall@k` per language (`en`, `ar`, `pga`)
   across candidate model pairs (`BGE-M3`, `Qwen3-Embedding + Qwen3-Reranker`, `multilingual-e5`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PGVECTOR_ITERATIVE_SCAN_SQL = "SET LOCAL hnsw.iterative_scan = 'relaxed_order';"


def build_pgvector_hybrid_rrf_sql() -> str:
    """Return parameterized SQL for hybrid FTS + pgvector HNSW retrieval filtered by published snapshot."""
    return """
    WITH lexical AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_tsv, plainto_tsquery('simple', :query)) DESC) AS r_lex
        FROM knowledge_chunks
        WHERE snapshot_version = :snapshot_version
          AND language = :language
          AND effective_from <= :as_of_date
          AND (effective_to IS NULL OR :as_of_date <= effective_to)
          AND search_tsv @@ plainto_tsquery('simple', :query)
        LIMIT :candidate_pool
    ),
    dense AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> :query_embedding) AS r_vec
        FROM knowledge_chunks
        WHERE snapshot_version = :snapshot_version
          AND language = :language
          AND effective_from <= :as_of_date
          AND (effective_to IS NULL OR :as_of_date <= effective_to)
        ORDER BY embedding <=> :query_embedding
        LIMIT :candidate_pool
    )
    SELECT c.id, c.doc_title, c.section_anchor, c.language, c.effective_from, c.content,
           COALESCE(1.0 / (:rrf_k + l.r_lex), 0.0) + COALESCE(1.0 / (:rrf_k + d.r_vec), 0.0) AS rrf_score
    FROM knowledge_chunks c
    LEFT JOIN lexical l ON c.id = l.id
    LEFT JOIN dense d ON c.id = d.id
    WHERE l.id IS NOT NULL OR d.id IS NOT NULL
    ORDER BY rrf_score DESC
    LIMIT :top_k;
    """.strip()


def reciprocal_rank_fusion(
    lexical_ids: list[str],
    dense_ids: list[str],
    *,
    rrf_k: int = 60,
    top_k: int = 5,
) -> list[tuple[str, float]]:
    """Fuse lexical and dense ranked ID lists using Reciprocal Rank Fusion (RRF)."""
    scores: dict[str, float] = {}
    for rank_idx, doc_id in enumerate(lexical_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank_idx))
    for rank_idx, doc_id in enumerate(dense_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank_idx))

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(doc_id, round(score, 6)) for doc_id, score in ranked[:top_k]]


@dataclass(frozen=True)
class BakeoffCandidateResult:
    candidate_name: str
    recall_at_k_by_locale: dict[str, float]
    mean_recall_at_k: float
    meets_parity_gate: bool


def evaluate_embedding_reranker_bakeoff(
    candidate_runs: dict[str, list[dict[str, Any]]],
    *,
    k: int = 3,
) -> list[BakeoffCandidateResult]:
    """Evaluate embedding + reranker candidates by recall@k per language (Section 7)."""
    results: list[BakeoffCandidateResult] = []
    for name, items in candidate_runs.items():
        by_loc: dict[str, list[int]] = {}
        for item in items:
            loc = str(item["locale"])
            expected_id = str(item["expected_chunk_id"])
            retrieved_top_k = list(item["retrieved_chunk_ids"])[:k]
            hit = 1 if expected_id in retrieved_top_k else 0
            by_loc.setdefault(loc, []).append(hit)

        loc_recalls = {loc: round(sum(hits) / max(1, len(hits)), 4) for loc, hits in by_loc.items()}
        mean_rec = round(
            sum(loc_recalls.values()) / max(1, len(loc_recalls)),
            4,
        )
        en_rec = loc_recalls.get("en", 1.0)
        parity_ok = all((en_rec - r) <= 0.05 for r in loc_recalls.values())
        results.append(
            BakeoffCandidateResult(
                candidate_name=name,
                recall_at_k_by_locale=loc_recalls,
                mean_recall_at_k=mean_rec,
                meets_parity_gate=parity_ok,
            )
        )

    results.sort(key=lambda r: r.mean_recall_at_k, reverse=True)
    return results
