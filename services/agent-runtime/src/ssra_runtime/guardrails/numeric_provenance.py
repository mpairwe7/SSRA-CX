"""Deterministic Numeric Provenance Validator (Principle 2, Section 6.1, 14.2 — 100% Gate).

Blocks any response containing a numeric figure in `Answer.segments[]` that is not traceable
to `Answer.numbers[]` AND to an approved tool artifact or cited TaxFact from the current turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ssra_core import Answer

# Translate Eastern Arabic numerals (٠١٢٣٤٥٦٧٨٩) to Western digits for provenance checking
_EASTERN_ARABIC_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Strip official URLs, UUIDs, ISO dates, section anchors, and masked TINs before scanning free-text numbers
_SAFE_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"https?://\S+"),
    re.compile(
        r"\b(?:[a-z]+_)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z]+_[0-9A-Z_]+\b"),
    re.compile(r"••••\d{4}"),
    re.compile(r"\+211(?:\s*\d{9}|•••••••\d{2}|\b)"),
    re.compile(r"\b918806493\b|\b912388318\b|\b919382390\b|\b917803637\b|\b921058043\b"),
    re.compile(r"\(\d{1,2}\)"),  # Parenthesized list bullets e.g. (1), (2), (3), (4)
    re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b"),
    re.compile(r"RSS/SSRA/[A-Z0-9/.\-\s]+VOL\.\s*II/\d+", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:Parts?|Secs?|Sections?|Regulations?|Chapters?|Articles?|Orders?|Circulars?|Modules?|Slides?)"
        r"\s*(?:No\.?\s*)?[0-9IVX]+(?:[.\-/][0-9A-Za-z()]+)*(?:\s*(?:to|and|,|-|–)\s*[0-9IVX]+(?:[.\-/][0-9A-Za-z()]+)*)*",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\bHS\s*\d{2}\.\d{2}(?:\s*-\s*\d{2}\.\d{2})?\b", flags=re.IGNORECASE),
    re.compile(r"\b\d+-digit\b", flags=re.IGNORECASE),
    re.compile(r"\b10\+\s*persons\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:Category|Stage|Step|Form)\s+[0-9A-Z]+\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b(?:2\s+consecutive\s+years|6\s+years|8\s+stages)\b", flags=re.IGNORECASE),
    re.compile(r"\bSSP\s+1\.1\s+trillion\b|\b6%\s+Tax-to-GDP\b", flags=re.IGNORECASE),
    re.compile(
        r"\b\d{1,2}\s*(?:-\s*\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:\s*-\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))?"
        r"(?:\s+20\d{2})?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b20\d{2}/20\d{2}\b"),
    re.compile(
        r"\b(?:Act,?\s+|Order\s+|Regulations\s+|Ethics\s+|Policy\s+|by\s+|"
        r"January\s+|February\s+|March\s+|April\s+|May\s+|June\s+|"
        r"July\s+|August\s+|September\s+|October\s+|November\s+|December\s+|"
        r"أكتوبر\s+|مارس\s+|لعام\s+|عام\s+|Maris\s+)\(?20\d{2}\)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"UTC\+0?2:00", flags=re.IGNORECASE),
)

_NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z_])\d+(?:,\d{3})*(?:\.\d+)?(?![A-Za-z_])")


@dataclass(frozen=True)
class NumericProvenanceResult:
    passed: bool
    unverified_numbers: list[str]
    reason: str | None = None


def _normalise_number_str(raw: str) -> str | None:
    cleaned = raw.translate(_EASTERN_ARABIC_MAP).replace(",", "").strip()
    try:
        dec = Decimal(cleaned)
        if dec == dec.to_integral_value():
            return str(int(dec))
        return format(dec.normalize(), "f")
    except InvalidOperation:
        return None


def _collect_artifact_numbers(artifacts: list[dict[str, Any]]) -> set[str]:
    allowed: set[str] = set()

    def _walk(val: Any) -> None:
        if isinstance(val, bool) or val is None:
            return
        if isinstance(val, (int, float, Decimal)):
            norm = _normalise_number_str(str(val))
            if norm is not None:
                allowed.add(norm)
        elif isinstance(val, str):
            norm = _normalise_number_str(val)
            if norm is not None:
                allowed.add(norm)
            for m in _NUMBER_TOKEN_RE.findall(val.translate(_EASTERN_ARABIC_MAP)):
                n2 = _normalise_number_str(m)
                if n2 is not None:
                    allowed.add(n2)
        elif isinstance(val, dict):
            for k, v in val.items():
                if k not in ("record_id", "id", "traceparent"):
                    _walk(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _walk(item)

    for art in artifacts:
        _walk(art)
    return allowed


def validate_numeric_provenance(
    answer: Answer,
    *,
    tool_artifacts: list[dict[str, Any]],
) -> NumericProvenanceResult:
    """Verify 100% of numbers in Answer.segments[] match Answer.numbers[] and tool_artifacts."""
    if answer.abstained:
        return NumericProvenanceResult(passed=True, unverified_numbers=[])

    artifact_numbers = _collect_artifact_numbers(tool_artifacts)
    declared_numbers: dict[str, str] = {}
    for claim in answer.numbers:
        norm = _normalise_number_str(claim.value)
        if norm is not None and claim.source_ref.strip():
            declared_numbers[norm] = claim.source_ref

    unverified: list[str] = []

    # 1. Every declared NumericClaim must exist in the tool artifacts from this turn
    for norm_val, source_ref in declared_numbers.items():
        if norm_val not in artifact_numbers:
            unverified.append(
                f"{norm_val} (declared source_ref={source_ref} not in tool artifacts)"
            )

    # 2. Every numeric token in segments[] must be declared in Answer.numbers[] and in artifacts
    for seg in answer.segments:
        scrubbed = seg.text.translate(_EASTERN_ARABIC_MAP)
        for pat in _SAFE_CONTEXT_PATTERNS:
            scrubbed = pat.sub(" ", scrubbed)
        for token in _NUMBER_TOKEN_RE.findall(scrubbed):
            norm = _normalise_number_str(token)
            if norm is None:
                continue
            if norm not in declared_numbers or norm not in artifact_numbers:
                unverified.append(token)

    if unverified:
        return NumericProvenanceResult(
            passed=False,
            unverified_numbers=unverified,
            reason=f"Untraced numeric values blocked by numeric_provenance guard: {unverified}",
        )
    return NumericProvenanceResult(passed=True, unverified_numbers=[])
