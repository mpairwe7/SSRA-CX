"""Hybrid retrieval coordinator combining lexical/dense candidates, filters, and reranking."""

from __future__ import annotations

from datetime import date
from typing import Any

from ssra_runtime.retrieval.filters import filter_published_chunks
from ssra_runtime.retrieval.rerank import rerank_chunks


def postprocess_retrieved_chunks(
    raw_chunks: list[dict[str, Any]],
    *,
    query: str,
    locale: str,
    snapshot_version: str = "2026.10.1",
    as_of: date | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    target_date = as_of or date(2026, 10, 16)
    filtered = filter_published_chunks(
        raw_chunks,
        snapshot_version=snapshot_version,
        as_of=target_date,
    )
    return rerank_chunks(filtered, query=query, locale=locale, top_k=top_k)
