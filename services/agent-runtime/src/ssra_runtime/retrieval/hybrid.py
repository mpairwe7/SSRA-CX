"""Hybrid retrieval coordinator combining lexical/dense candidates, filters, and reranking."""

from __future__ import annotations

from datetime import date
from typing import Any

from ssra_core import juba_today

from ssra_runtime.guardrails.grounding import detect_conflicting_chunks
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
    target_date = as_of or juba_today()
    filtered = filter_published_chunks(
        raw_chunks,
        snapshot_version=snapshot_version,
        as_of=target_date,
    )
    conflicts = detect_conflicting_chunks(filtered)
    if conflicts:
        by_anchor_lang: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for chk in filtered:
            if chk.get("effective_to") is not None:
                continue
            key = (str(chk.get("section_anchor", "")), str(chk.get("language", "en")))
            if key[0]:
                by_anchor_lang.setdefault(key, []).append(chk)
        conflicted_keys = {
            key
            for key, group in by_anchor_lang.items()
            if len(group) > 1
            and (
                len({str(g.get("effective_from", "")) for g in group}) > 1
                or len({str(g.get("content", "")) for g in group}) > 1
            )
        }
        filtered = [
            chk
            for chk in filtered
            if (str(chk.get("section_anchor", "")), str(chk.get("language", "en")))
            not in conflicted_keys
        ]
    return rerank_chunks(filtered, query=query, locale=locale, top_k=top_k)
