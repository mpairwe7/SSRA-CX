"""Retrieval package."""

from ssra_runtime.retrieval.filters import filter_published_chunks
from ssra_runtime.retrieval.hybrid import postprocess_retrieved_chunks
from ssra_runtime.retrieval.pgvector_hybrid import (
    PGVECTOR_ITERATIVE_SCAN_SQL,
    BakeoffCandidateResult,
    build_pgvector_hybrid_rrf_sql,
    evaluate_embedding_reranker_bakeoff,
    reciprocal_rank_fusion,
)
from ssra_runtime.retrieval.rerank import rerank_chunks

__all__ = [
    "PGVECTOR_ITERATIVE_SCAN_SQL",
    "BakeoffCandidateResult",
    "build_pgvector_hybrid_rrf_sql",
    "evaluate_embedding_reranker_bakeoff",
    "filter_published_chunks",
    "postprocess_retrieved_chunks",
    "reciprocal_rank_fusion",
    "rerank_chunks",
]
