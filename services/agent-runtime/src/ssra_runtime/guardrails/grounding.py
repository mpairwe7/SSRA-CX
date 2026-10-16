"""Claim-to-source groundedness validator (Principle 1, Section 6.1, 14.2)."""

from __future__ import annotations

from dataclasses import dataclass

from ssra_core import Answer


@dataclass(frozen=True)
class GroundingResult:
    passed: bool
    reason: str | None = None


def validate_grounding(answer: Answer) -> GroundingResult:
    """Ensure every non-abstained factual Answer cites at least one approved source."""
    if answer.abstained:
        return GroundingResult(passed=True)

    if not answer.citations:
        return GroundingResult(
            passed=False,
            reason="Non-abstained answer has zero citations (Principle 1: Grounded or silent)",
        )

    valid_ids = {c.id for c in answer.citations if c.doc_title and c.section_anchor}
    if not valid_ids:
        return GroundingResult(
            passed=False,
            reason="Citations are missing required doc_title or section_anchor",
        )

    for seg in answer.segments:
        if not seg.citation_ids or not any(cid in valid_ids for cid in seg.citation_ids):
            return GroundingResult(
                passed=False,
                reason=f"Segment '{seg.text[:40]}...' lacks a valid citation_id reference",
            )
    return GroundingResult(passed=True)
