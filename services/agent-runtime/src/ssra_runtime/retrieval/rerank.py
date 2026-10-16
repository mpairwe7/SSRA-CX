"""Multilingual & Cross-Lingual Termbase-Enriched Reranker for Retrieved Legal Chunks (Section 7)."""

from __future__ import annotations

import re
from typing import Any

from ssra_core import expand_ssra_nra_synonyms
from ssra_llm import load_termbase

_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def expand_query_with_multilingual_termbase(query: str) -> str:
    """Expand complete localized/Creole/Nilotic tax phrases to canonical English statutory keywords via glossary.yaml."""
    expanded = expand_ssra_nra_synonyms(query)
    lower_q = expanded.lower()
    tb = load_termbase()
    extra_keywords: list[str] = []
    for entry in tb.get("terms", []):
        if not isinstance(entry, dict):
            continue
        en_term = str(entry.get("en", ""))
        matched = False
        for loc_key in ("ar", "pga", "din", "nus", "bfa", "zne", "shk"):
            loc_val = str(entry.get(loc_key, "")).lower().strip()
            bare_phrase = _TRAILING_PAREN_RE.sub("", loc_val).strip()
            if (loc_val and loc_val in lower_q) or (
                len(bare_phrase) >= 6 and bare_phrase in lower_q
            ):
                matched = True
                break
        if matched and en_term and en_term.lower() not in lower_q:
            extra_keywords.append(en_term)
    if extra_keywords:
        return f"{expanded} {' '.join(extra_keywords)}"
    return expanded


def rerank_chunks(
    chunks: list[dict[str, Any]],
    *,
    query: str,
    locale: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    expanded = expand_query_with_multilingual_termbase(query).lower()
    terms = [t for t in expanded.split() if len(t) >= 2]

    def _score(chk: dict[str, Any]) -> int:
        text = f"{chk.get('doc_title', '')} {chk.get('section_anchor', '')} {chk.get('content', '')}".lower()
        score = sum(4 if t in text else 0 for t in terms)
        if chk.get("language") == locale:
            score += 5
        return score

    ranked = sorted(chunks, key=_score, reverse=True)
    return ranked[:top_k]
