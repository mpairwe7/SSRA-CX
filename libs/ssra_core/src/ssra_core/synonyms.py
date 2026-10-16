"""Synonym normalisation for SSRA and legacy NRA naming (Section 2)."""

from __future__ import annotations

import re

_NRA_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bNational\s+Revenue\s+Authority\b", flags=re.IGNORECASE),
        "South Sudan Revenue Authority (SSRA, formerly NRA)",
    ),
    (
        re.compile(r"\bNRA\b"),
        "SSRA (NRA)",
    ),
)


def expand_ssra_nra_synonyms(query: str) -> str:
    """Expand NRA/SSRA synonyms in search queries so legacy NRA references match SSRA content."""
    lower = query.lower()
    has_nra = "nra" in lower or "national revenue authority" in lower
    has_ssra = "ssra" in lower or "south sudan revenue authority" in lower
    if has_nra and not has_ssra:
        return f"{query} SSRA South Sudan Revenue Authority"
    if has_ssra and not has_nra:
        return f"{query} NRA National Revenue Authority"
    return query


def normalise_authority_mentions(text: str) -> str:
    """Ensure legacy NRA mentions clarify the October 2023 rename to SSRA while preserving URLs."""
    tokens = text.split(" ")
    out: list[str] = []
    for tok in tokens:
        if "etax.nra.gov.ss" in tok or "cms.nra.gov.ss" in tok or "http" in tok:
            out.append(tok)
            continue
        updated = tok
        for pattern, replacement in _NRA_PATTERNS:
            updated = pattern.sub(replacement, updated)
        out.append(updated)
    return " ".join(out)
