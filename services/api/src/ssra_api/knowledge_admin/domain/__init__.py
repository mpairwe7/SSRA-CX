"""Domain layer for knowledge_admin bounded context (6-step Knowledge Release workflow with Maker-Checker separation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSnapshotEntity:
    version: str
    status: str  # DRAFT | LEGAL_REVIEW | APPROVED | PUBLISHED | ROLLED_BACK
    approved_by: str
    checksum: str
    created_by: str = "policy_author_default"
