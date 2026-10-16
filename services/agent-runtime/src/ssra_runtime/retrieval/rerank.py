"""Multilingual reranker for retrieved legal chunks (Section 7)."""

from __future__ import annotations

from typing import Any

from ssra_core import expand_ssra_nra_synonyms


def rerank_chunks(
    chunks: list[dict[str, Any]],
    *,
    query: str,
    locale: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    expanded = expand_ssra_nra_synonyms(query).lower()
    terms = [t for t in expanded.split() if len(t) >= 2]

    def _score(chk: dict[str, Any]) -> int:
        text = f"{chk.get('doc_title', '')} {chk.get('section_anchor', '')} {chk.get('content', '')}".lower()
        score = sum(4 if t in text else 0 for t in terms)
        if chk.get("language") == locale:
            score += 5
        return score

    ranked = sorted(chunks, key=_score, reverse=True)
    return ranked[:top_k]
