"""Claim-to-source groundedness & attribution warrant validator (Principle 1, Section 6.1, 14.2, ClaimRAG-Law arXiv:2605.21071)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ssra_core import Answer

_DETERMINISTIC_TOOL_CITATION_IDS: frozenset[str] = frozenset(
    {
        "cit_paye_act",
        "cit_wht_act",
        "cit_customs_act",
        "cit_customs_tariff",
        "cit_ecustoms_declaration",
        "cit_cashfree_2026",
        "cit_etax_ledger",
        "cit_etax_filing",
        "cit_etax_tcc",
        "cit_scam_case",
        "cit_appt_confirm",
        "cit_case_confirm",
    }
)


@dataclass(frozen=True)
class GroundingResult:
    passed: bool
    reason: str | None = None


def detect_conflicting_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    """Detect conflicting active statutory chunks sharing the same (section_anchor, language) without supersession."""
    by_anchor_lang: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for chk in chunks:
        if chk.get("effective_to") is not None:
            continue
        key = (str(chk.get("section_anchor", "")), str(chk.get("language", "en")))
        if key[0]:
            by_anchor_lang.setdefault(key, []).append(chk)

    conflicts: list[str] = []
    for (anchor, lang), group in by_anchor_lang.items():
        eff_dates = {str(g.get("effective_from", "")) for g in group}
        contents = {str(g.get("content", "")) for g in group}
        if len(group) > 1 and (len(eff_dates) > 1 or len(contents) > 1):
            conflicts.append(
                f"Conflicting active chunks for section_anchor='{anchor}' (lang='{lang}'): "
                f"effective_from={sorted(eff_dates)}"
            )
    return conflicts


def validate_grounding(
    answer: Answer,
    *,
    tool_artifacts: list[dict[str, Any]] | None = None,
) -> GroundingResult:
    """Ensure every non-abstained Answer cites approved sources and matches turn evidence (ClaimRAG-Law 2026)."""
    if answer.abstained:
        return GroundingResult(passed=True)

    if not answer.citations:
        return GroundingResult(
            passed=False,
            reason="Non-abstained answer has zero citations (Principle 1: Grounded or silent)",
        )

    valid_ids = {
        c.id
        for c in answer.citations
        if c.doc_title and c.section_anchor and c.snapshot_version and c.effective_from
    }
    if not valid_ids:
        return GroundingResult(
            passed=False,
            reason="Citations are missing required doc_title, section_anchor, snapshot_version, or effective_from",
        )

    # Verify citation existence and non-contradiction against the current turn's retrieved chunks / tool artifacts
    if tool_artifacts is not None:
        artifact_chunk_ids: set[str] = set()
        allowed_anchors: set[str] = set()
        for art in tool_artifacts:
            results = art.get("results")
            if isinstance(results, list):
                dict_results = [r for r in results if isinstance(r, dict)]
                conflicts = detect_conflicting_chunks(dict_results)
                if conflicts:
                    return GroundingResult(
                        passed=False,
                        reason=conflicts[0],
                    )
                for r in dict_results:
                    if "id" in r:
                        artifact_chunk_ids.add(str(r["id"]))
                    if "section_anchor" in r:
                        allowed_anchors.add(str(r["section_anchor"]))
            sec = art.get("section")
            if isinstance(sec, dict):
                if "id" in sec:
                    artifact_chunk_ids.add(str(sec["id"]))
                if "section_anchor" in sec:
                    allowed_anchors.add(str(sec["section_anchor"]))

        allowed_evidence_ids = set(_DETERMINISTIC_TOOL_CITATION_IDS) | artifact_chunk_ids
        for cit in answer.citations:
            if artifact_chunk_ids:
                if cit.id not in allowed_evidence_ids:
                    return GroundingResult(
                        passed=False,
                        reason=f"Citation ID '{cit.id}' was not present in turn tool artifacts",
                    )
            else:
                if cit.id not in allowed_evidence_ids and cit.section_anchor not in allowed_anchors:
                    return GroundingResult(
                        passed=False,
                        reason=f"Citation '{cit.id}' ('{cit.section_anchor}') was not present in turn tool artifacts",
                    )

    for seg in answer.segments:
        if not seg.text.strip():
            return GroundingResult(
                passed=False,
                reason="Answer segment text is empty",
            )
        if not seg.citation_ids or not any(cid in valid_ids for cid in seg.citation_ids):
            return GroundingResult(
                passed=False,
                reason=f"Segment '{seg.text[:40]}...' lacks a valid citation_id reference",
            )
    return GroundingResult(passed=True)
