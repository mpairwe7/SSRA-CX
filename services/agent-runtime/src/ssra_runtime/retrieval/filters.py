"""Metadata filters for hybrid retrieval (Section 7)."""

from __future__ import annotations

from datetime import date
from typing import Any


def filter_published_chunks(
    chunks: list[dict[str, Any]],
    *,
    snapshot_version: str,
    as_of: date,
    audience: str = "PUBLIC",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for chk in chunks:
        if chk.get("audience", "PUBLIC") != audience:
            continue
        eff_from_str = str(chk.get("effective_from", "1970-01-01"))
        eff_from = date.fromisoformat(eff_from_str)
        if eff_from > as_of:
            continue
        eff_to_raw = chk.get("effective_to")
        if eff_to_raw:
            eff_to = date.fromisoformat(str(eff_to_raw))
            if as_of > eff_to:
                continue
        out.append(chk)
    _ = snapshot_version
    return out
